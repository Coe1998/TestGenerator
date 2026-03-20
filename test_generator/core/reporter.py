"""
core/reporter.py
================
Invia facoltativamente il riepilogo di ogni sessione a un server centrale aziendale.

Abilitato SOLO se la variabile di sistema TESTGEN_CENTRAL_URL è configurata.
Se il server non è raggiungibile, fallisce silenziosamente senza bloccare il workflow.

Struttura del payload inviato a POST /api/ingest:
{
    "session_id":       "a3f1c9b82d04",
    "timestamp":        "2026-03-19T10:30:00+00:00",
    "hostname":         "LAPTOP-XYZ",         # identifica la macchina del collega
    "framework":        "mstest",
    "model":            "gemini-2.5-flash",
    "total_files":      5,
    "ok_count":         4,
    "fail_count":       1,
    "total_scenarios":  60,
    "total_ai_ms":      11200,
    "bulk":             False,
    "app_version":      "1.0.0",
}
"""
import json
import socket
import urllib.request
import urllib.error
from datetime import datetime, timezone

from dashboard.settings import CENTRAL_API_URL

APP_VERSION = "1.0.0"


def report_session(
    session_id:      str,
    framework:       str,
    model:           str,
    total_files:     int,
    ok_count:        int,
    fail_count:      int,
    total_scenarios: int,
    total_ai_ms:     int,
    bulk:            bool,
) -> None:
    """
    Invia il riepilogo della sessione al server centrale (se configurato).
    Non lancia mai eccezioni: la funzione è best-effort.
    """
    if not CENTRAL_API_URL:
        return

    payload = {
        "session_id":       session_id,
        "timestamp":        datetime.now(tz=timezone.utc).isoformat(),
        "hostname":         _safe_hostname(),
        "framework":        framework,
        "model":            model,
        "total_files":      total_files,
        "ok_count":         ok_count,
        "fail_count":       fail_count,
        "total_scenarios":  total_scenarios,
        "total_ai_ms":      total_ai_ms,
        "bulk":             bulk,
        "app_version":      APP_VERSION,
    }

    try:
        data = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
        req = urllib.request.Request(
            f"{CENTRAL_API_URL}/api/ingest",
            data=data,
            headers={"Content-Type": "application/json", "X-App": "testgenerator"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5):
            pass
    except Exception:
        pass  # Silenzioso — non interrompe mai il workflow


def _safe_hostname() -> str:
    try:
        return socket.gethostname()
    except Exception:
        return "unknown"
