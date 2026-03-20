"""
dashboard/settings.py
=====================
Configurazione del dashboard di analisi.
Tutti i valori sono sovrastati da variabili di sistema, così ogni collega
può personalizzare senza modificare il codice.
"""
import os

# Porta del server dashboard locale
DASHBOARD_PORT: int = int(os.getenv("TESTGEN_DASHBOARD_PORT", "5050"))

# Minuti stimati per scrivere manualmente UN scenario di test
# (analisi, scrittura, esecuzione, debug, review)
MANUAL_MINUTES_PER_SCENARIO: int = int(os.getenv("TESTGEN_MANUAL_MINUTES", "20"))

# Ore lavorative per giorno (usato per convertire ore in giorni)
WORKDAY_HOURS: int = int(os.getenv("TESTGEN_WORKDAY_HOURS", "8"))

# URL del server centrale aziendale (vuoto = funzionalità disabilitata)
# Esempio: "https://analytics.mycompany.com"
CENTRAL_API_URL: str = os.getenv("TESTGEN_CENTRAL_URL", "").rstrip("/")
