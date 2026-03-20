"""
core/logger.py
==============
Sistema di logging strutturato per TestGenerator.

Formato: JSONL (JSON Lines) — una riga JSON per evento.
File  : %APPDATA%\TestGenerator\logs\testgenerator.jsonl
        (rotazione automatica a 5 MB, massimo 5 file storici)
        Override: variabile di sistema TESTGEN_LOG_DIR

Struttura di ogni riga:
{
    "timestamp"  : "2026-03-19T10:30:00.123+00:00",  # ISO 8601 UTC
    "session_id" : "a3f1c9b82d04",                    # univoco per ogni run
    "level"      : "INFO",                            # DEBUG | INFO | WARNING | ERROR
    "event"      : "ai_call_complete",                # nome evento strutturato
    "duration_ms": 2341,                              # (solo eventi con timing)
    "file"       : "OrderService.cs",
    "framework"  : "xunit",
    "model"      : "gemini-2.5-flash",
    "scenarios"  : 12,
    "output_path": "...",
    "error"      : "...",                             # (solo eventi di errore)
    "traceback"  : "...",                             # (solo in caso di eccezione)
    ...
}

API pubblica:
    init_session(**context)          → str (session_id)
    end_session(ok, fail)
    log_event(level, event, **extra)
    log_error(event, exc, **extra)
    log_timing(event, **extra)       → context manager
"""

import sys
import json
import time
import uuid
import logging
import traceback
from datetime import datetime, timezone
from pathlib import Path
from contextlib import contextmanager
from logging.handlers import RotatingFileHandler

# ---------------------------------------------------------------------------
# Percorso log — unico e fisso indipendentemente da dove viene lanciato
# il programma (.exe, python main.py, dashboard, ecc.)
#
# Percorso: %APPDATA%\TestGenerator\logs\testgenerator.jsonl
#   es. C:\Users\mario\AppData\Roaming\TestGenerator\logs\
#
# Override: imposta la variabile di sistema TESTGEN_LOG_DIR per usare
#   un percorso personalizzato (es. cartella di rete condivisa).
# ---------------------------------------------------------------------------
import os as _os

_DEFAULT_LOG_DIR = Path(_os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming")) \
                   / "TestGenerator" / "logs"

LOG_DIR  = Path(_os.environ.get("TESTGEN_LOG_DIR", str(_DEFAULT_LOG_DIR)))
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "testgenerator.jsonl"

# Campi extra riconosciuti che vengono estratti e aggiunti all'entry JSON
_EXTRA_FIELDS = (
    "file", "file_path", "framework", "model",
    "duration_ms", "scenarios", "output_path",
    "error", "ok_count", "fail_count", "total",
    "inputs", "recursive", "bulk",
)

# ---------------------------------------------------------------------------
# Handler personalizzato — scrive JSONL con rotazione
# ---------------------------------------------------------------------------
class _JsonlFormatter(logging.Formatter):
    """Formatta ogni LogRecord come stringa JSON (senza newline finale)."""

    def format(self, record: logging.LogRecord) -> str:
        entry: dict = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "session_id": _session_id,
            "level": record.levelname,
            "event": record.getMessage(),
        }
        entry.update(_session_context)

        for key in _EXTRA_FIELDS:
            val = getattr(record, key, None)
            if val is not None:
                entry[key] = val

        if record.exc_info:
            entry["traceback"] = "".join(
                traceback.format_exception(*record.exc_info)
            ).strip()

        return json.dumps(entry, ensure_ascii=False)


class _JsonlHandler(RotatingFileHandler):
    """Scrive ogni LogRecord come riga JSON con rotazione automatica."""

    def __init__(self, filepath: Path):
        super().__init__(
            filename=str(filepath),
            maxBytes=5 * 1024 * 1024,  # 5 MB per file
            backupCount=5,
            encoding="utf-8",
        )
        self.setFormatter(_JsonlFormatter())
        # Il terminatore di riga è già "\n" per default in StreamHandler


# ---------------------------------------------------------------------------
# Setup interno
# ---------------------------------------------------------------------------
_session_id: str = ""
_session_context: dict = {}

_logger = logging.getLogger("testgenerator")
_logger.setLevel(logging.DEBUG)
_logger.propagate = False  # non duplicare sui logger root di Python

if not _logger.handlers:
    _logger.addHandler(_JsonlHandler(LOG_FILE))


# ---------------------------------------------------------------------------
# API pubblica
# ---------------------------------------------------------------------------

def init_session(**context) -> str:
    """
    Inizializza una nuova sessione. Chiamare UNA SOLA VOLTA all'avvio in main.py.

    Parametri suggeriti:
        framework   : str   ("mstest" | "xunit" | "nunit")
        inputs      : list  (file/cartelle passati da CLI)
        recursive   : bool
        bulk        : bool  (True se file_list > 1)

    Restituisce il session_id (utile per correlare log di sessioni diverse).
    """
    global _session_id, _session_context
    _session_id = uuid.uuid4().hex[:12]
    # Salva solo i campi non-None come contesto fisso della sessione
    _session_context = {k: v for k, v in context.items() if v is not None}
    _logger.info("session_start", extra=_session_context)
    return _session_id


def end_session(ok_count: int, fail_count: int) -> None:
    """Logga il termine della sessione con il riepilogo finale."""
    _logger.info(
        "session_end",
        extra={"ok_count": ok_count, "fail_count": fail_count, "total": ok_count + fail_count},
    )


def log_event(level: str, event: str, **extra) -> None:
    """
    Logga un evento generico.

    level : "debug" | "info" | "warning" | "error"
    event : nome strutturato, es. "bulk_confirm", "sln_update_skipped"
    extra : campi aggiuntivi da includere nella riga JSON
    """
    log_fn = getattr(_logger, level.lower(), _logger.info)
    log_fn(event, extra=extra)


def log_error(event: str, exc: BaseException | None = None, **extra) -> None:
    """
    Logga un errore, opzionalmente con l'eccezione originale.
    Se viene passata l'eccezione, il traceback viene incluso nel log.
    """
    extra_with_error = extra.copy()
    if exc is not None:
        extra_with_error["error"] = str(exc)
    _logger.error(event, exc_info=exc if exc is not None else False, extra=extra_with_error)


@contextmanager
def log_timing(event: str, **extra):
    """
    Context manager che misura la durata di un blocco e la registra nel log.

    Genera tre eventi:
        {event}_start    — DEBUG  (prima dell'operazione)
        {event}_complete — INFO   (dopo, con duration_ms)
        {event}_error    — ERROR  (se viene lanciata un'eccezione, con duration_ms + traceback)

    L'eccezione viene ri-lanciata invariata dopo il log.

    Uso:
        with log_timing("ai_call", file="MyClass.cs", model="gemini-2.5-flash"):
            result = call_gemini(...)
    """
    _logger.debug(f"{event}_start", extra=extra)
    start = time.perf_counter()
    try:
        yield
        duration_ms = round((time.perf_counter() - start) * 1000)
        _logger.info(f"{event}_complete", extra={**extra, "duration_ms": duration_ms})
    except Exception as exc:
        duration_ms = round((time.perf_counter() - start) * 1000)
        _logger.error(
            f"{event}_error",
            exc_info=exc,
            extra={**extra, "duration_ms": duration_ms, "error": str(exc)},
        )
        raise
