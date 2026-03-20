"""
dashboard/server.py
===================
Server Flask per il dashboard di analisi locale.
Compatibile con PyInstaller: risolve il percorso dei template
sia in modalità script che in modalità .exe compilato.
"""
import sys
import threading
import webbrowser
from pathlib import Path

from flask import Flask, jsonify, render_template

from dashboard.analyzer import load_events, compute_stats
from dashboard.settings import DASHBOARD_PORT

# ---------------------------------------------------------------------------
# Compatibilità PyInstaller per il percorso dei template
# ---------------------------------------------------------------------------
if getattr(sys, "frozen", False):
    _template_dir = Path(sys.executable).parent / "dashboard" / "templates"
else:
    _template_dir = Path(__file__).parent / "templates"

app = Flask(__name__, template_folder=str(_template_dir))
app.config["JSON_SORT_KEYS"] = False


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/stats")
def api_stats():
    events = load_events()
    return jsonify(compute_stats(events))


@app.route("/api/health")
def api_health():
    return jsonify({"status": "ok", "port": DASHBOARD_PORT})


# ---------------------------------------------------------------------------
# Avvio
# ---------------------------------------------------------------------------

def run(port: int = DASHBOARD_PORT, open_browser: bool = True) -> None:
    """
    Avvia il server Flask in modalità bloccante.
    Apre automaticamente il browser dopo 1 secondo.
    Chiamare con `python main.py --dashboard` oppure `main.exe --dashboard`.
    """
    url = f"http://localhost:{port}"
    print(f"\n{'='*50}")
    print(f"  TestGenerator Analytics Dashboard")
    print(f"  {url}")
    print(f"{'='*50}")
    print("  Premi Ctrl+C per fermare il server.\n")

    if open_browser:
        threading.Timer(1.2, lambda: webbrowser.open(url)).start()

    app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False)
