import sys
import io
import os  # <--- Necessario per leggere le variabili d'ambiente
import tree_sitter_c_sharp as csharp
from tree_sitter import Language
from openai import OpenAI # <--- Assicurati di aver fatto: pip install openai

# Forza UTF-8 per console Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

CS_LANG = Language(csharp.language())

# ======================================
# CONFIGURAZIONE OPENAI
# ======================================

# Recupera la chiave dalla variabile di sistema "OPENAI_API_KEY"
api_key = os.getenv("OPENAI_API_KEY")

if not api_key:
    print("ERRORE: Variabile di sistema 'OPENAI_API_KEY' non trovata.")
    sys.exit(1)

# Inizializza il client OpenAI
client = OpenAI(api_key=api_key)

# Modelli consigliati: "gpt-4o" (più intelligente) o "gpt-4o-mini" (più veloce ed economico)
OPENAI_MODEL = "gpt-4o" 

# ======================================
# SEVERITY MAP (centralizzata)
# ======================================

SEVERITY_MAP = {
    "OUTPUT":      "HIGH",
    "SIDE_EFFECT": "MEDIUM",
    "LOGIC":       "HIGH",
    "EXCEPTION":   "HIGH",
    "INPUT":       "HIGH",
    "BOUNDARY":    "MEDIUM",
}