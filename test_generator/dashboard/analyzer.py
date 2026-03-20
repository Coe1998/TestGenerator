"""
dashboard/analyzer.py
=====================
Legge il file JSONL dei log e calcola tutte le statistiche necessarie
per il dashboard. Nessuna dipendenza da config.py o dall'API key.
"""
import json
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

from core.logger import LOG_FILE
from dashboard.settings import MANUAL_MINUTES_PER_SCENARIO, WORKDAY_HOURS


# ---------------------------------------------------------------------------
# Caricamento raw
# ---------------------------------------------------------------------------

def load_events() -> list[dict]:
    """Legge tutte le righe JSONL dal file di log. Ignora le righe malformate."""
    if not LOG_FILE.exists():
        return []
    events = []
    with open(LOG_FILE, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return events


# ---------------------------------------------------------------------------
# Ricostruzione sessioni
# ---------------------------------------------------------------------------

def _build_sessions(events: list[dict]) -> list[dict]:
    """
    Raggruppa gli eventi per session_id e ricostruisce un riepilogo per
    ciascuna sessione, anche se la sessione è stata interrotta (nessun
    evento session_end).
    """
    by_session: dict[str, list[dict]] = defaultdict(list)
    for e in events:
        sid = e.get("session_id") or "unknown"
        by_session[sid].append(e)

    sessions = []
    for sid, evts in by_session.items():
        evts = sorted(evts, key=lambda e: e.get("timestamp", ""))

        def first(event_name: str) -> dict:
            return next((e for e in evts if e.get("event") == event_name), {})

        start = first("session_start") or evts[0]
        end   = first("session_end")

        ai_done     = [e for e in evts if e.get("event") == "ai_call_complete"]
        analyses    = [e for e in evts if e.get("event") == "file_analysis_complete"]
        scenario_evts = [e for e in evts if e.get("event") == "scenarios_found"]
        error_evts  = [e for e in evts if e.get("level") == "ERROR"]

        total_scenarios = sum(e.get("scenarios", 0) for e in scenario_evts)
        total_ai_ms     = sum(e.get("duration_ms", 0) for e in ai_done)
        total_analysis_ms = sum(e.get("duration_ms", 0) for e in analyses)

        timestamp = start.get("timestamp", "")
        ok_count   = end.get("ok_count", 0) if end else sum(
            1 for e in evts if e.get("event") == "full_generation_complete"
        )
        fail_count = end.get("fail_count", 0) if end else len(error_evts)

        sessions.append({
            "session_id":       sid,
            "timestamp":        timestamp,
            "date":             timestamp[:10],
            "framework":        start.get("framework", "unknown"),
            "model":            start.get("model", "unknown"),
            "bulk":             start.get("bulk", False),
            "ok_files":         ok_count,
            "fail_files":       fail_count,
            "total_files":      ok_count + fail_count,
            "total_scenarios":  total_scenarios,
            "total_ai_ms":      total_ai_ms,
            "avg_ai_ms":        total_ai_ms // len(ai_done) if ai_done else 0,
            "total_analysis_ms": total_analysis_ms,
            "error_count":      len(error_evts),
            "complete":         bool(end),
        })

    sessions.sort(key=lambda s: s.get("timestamp", ""))
    return sessions


# ---------------------------------------------------------------------------
# Calcolo statistiche aggregate
# ---------------------------------------------------------------------------

def compute_stats(events: list[dict]) -> dict:
    """
    Punto di ingresso principale: restituisce un dict strutturato pronto
    per essere serializzato in JSON e consumato dal frontend.
    """
    if not events:
        return _empty_stats()

    sessions = _build_sessions(events)

    # ---- Totali ----
    total_sessions  = len(sessions)
    total_files     = sum(s["total_files"]     for s in sessions)
    total_ok        = sum(s["ok_files"]        for s in sessions)
    total_scenarios = sum(s["total_scenarios"] for s in sessions)
    total_errors    = sum(s["error_count"]     for s in sessions)
    total_ai_ms     = sum(s["total_ai_ms"]     for s in sessions)
    success_rate    = round(total_ok / total_files * 100, 1) if total_files else 0.0

    # ---- Risparmio ----
    manual_minutes  = total_scenarios * MANUAL_MINUTES_PER_SCENARIO
    manual_hours    = round(manual_minutes / 60, 1)
    manual_days     = round(manual_hours / WORKDAY_HOURS, 1)
    ai_hours        = round(total_ai_ms / 3_600_000, 2)
    net_hours_saved = round(max(manual_hours - ai_hours, 0), 1)
    net_days_saved  = round(net_hours_saved / WORKDAY_HOURS, 1)

    # ---- Performance per framework ----
    by_framework: dict[str, int] = defaultdict(int)
    for s in sessions:
        by_framework[s["framework"] or "unknown"] += s["total_files"]

    # ---- Performance per modello ----
    by_model: dict[str, dict] = defaultdict(lambda: {"count": 0, "total_ms": 0})
    for e in events:
        if e.get("event") == "ai_call_complete":
            m = e.get("model", "unknown")
            by_model[m]["count"]    += 1
            by_model[m]["total_ms"] += e.get("duration_ms", 0)
    by_model_final = {
        m: {
            "count":  v["count"],
            "avg_ms": round(v["total_ms"] / v["count"]) if v["count"] else 0,
        }
        for m, v in by_model.items()
    }

    # ---- Media scenari per file ----
    avg_scenarios = round(total_scenarios / total_ok, 1) if total_ok else 0.0

    # ---- Timeline ultimi 30 giorni ----
    today = datetime.now()
    daily: dict[str, dict] = defaultdict(lambda: {"sessions": 0, "files": 0, "scenarios": 0})
    for s in sessions:
        d = s.get("date", "")
        if d:
            daily[d]["sessions"]  += 1
            daily[d]["files"]     += s["ok_files"]
            daily[d]["scenarios"] += s["total_scenarios"]

    timeline = []
    for i in range(29, -1, -1):
        d = (today - timedelta(days=i)).strftime("%Y-%m-%d")
        timeline.append({"date": d, **daily.get(d, {"sessions": 0, "files": 0, "scenarios": 0})})

    # ---- File più complessi (più scenari rilevati) ----
    file_max_scenarios: dict[str, int] = defaultdict(int)
    for e in events:
        if e.get("event") == "scenarios_found":
            fname = e.get("file", "unknown")
            file_max_scenarios[fname] = max(file_max_scenarios[fname], e.get("scenarios", 0))

    top_complex = sorted(
        [{"file": f, "scenarios": n} for f, n in file_max_scenarios.items()],
        key=lambda x: x["scenarios"],
        reverse=True,
    )[:10]

    # ---- Errori per tipo ----
    errors_by_event: dict[str, int] = defaultdict(int)
    for e in events:
        if e.get("level") == "ERROR":
            errors_by_event[e.get("event", "unknown")] += 1

    # ---- Sessioni recenti (ultime 15, dalla più recente) ----
    recent_sessions = [
        {
            "session_id": s["session_id"][:8],
            "timestamp":  s["timestamp"][:19].replace("T", " "),
            "framework":  s["framework"],
            "model":      s["model"],
            "files":      s["total_files"],
            "scenarios":  s["total_scenarios"],
            "ok":         s["ok_files"],
            "fail":       s["fail_files"],
            "ai_ms":      s["total_ai_ms"],
            "bulk":       s["bulk"],
            "complete":   s["complete"],
        }
        for s in reversed(sessions[-15:])
    ]

    return {
        "summary": {
            "total_sessions":  total_sessions,
            "total_files":     total_files,
            "total_ok":        total_ok,
            "total_scenarios": total_scenarios,
            "total_errors":    total_errors,
            "success_rate":    success_rate,
        },
        "savings": {
            "total_scenarios":             total_scenarios,
            "manual_minutes_per_scenario": MANUAL_MINUTES_PER_SCENARIO,
            "manual_hours":                manual_hours,
            "manual_days":                 manual_days,
            "ai_hours":                    ai_hours,
            "net_hours_saved":             net_hours_saved,
            "net_days_saved":              net_days_saved,
        },
        "performance": {
            "avg_scenarios_per_file": avg_scenarios,
            "avg_ai_ms":              round(total_ai_ms / total_ok) if total_ok else 0,
            "by_framework":           dict(by_framework),
            "by_model":               by_model_final,
        },
        "timeline":          timeline,
        "top_complex_files": top_complex,
        "recent_sessions":   recent_sessions,
        "errors_by_event":   dict(errors_by_event),
        "log_path":          str(LOG_FILE),
    }


def _empty_stats() -> dict:
    return {
        "summary": {
            "total_sessions": 0, "total_files": 0, "total_ok": 0,
            "total_scenarios": 0, "total_errors": 0, "success_rate": 0.0,
        },
        "savings": {
            "total_scenarios": 0,
            "manual_minutes_per_scenario": MANUAL_MINUTES_PER_SCENARIO,
            "manual_hours": 0.0, "manual_days": 0.0,
            "ai_hours": 0.0, "net_hours_saved": 0.0, "net_days_saved": 0.0,
        },
        "performance": {
            "avg_scenarios_per_file": 0.0, "avg_ai_ms": 0,
            "by_framework": {}, "by_model": {},
        },
        "timeline": [],
        "top_complex_files": [],
        "recent_sessions": [],
        "errors_by_event": {},
        "log_path": str(LOG_FILE),
    }
