import sys
import io
import os
import tree_sitter_c_sharp as csharp
from tree_sitter import Language
import google.generativeai as genai  # <--- Sostituito OpenAI con Gemini

# Forza UTF-8 per console Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

CS_LANG = Language(csharp.language())

# ======================================
# CONFIGURAZIONE GEMINI
# ======================================

# Recupera la chiave dalla variabile di sistema "GOOGLE_API_KEY"
api_key = os.getenv("GOOGLE_API_KEY")
GEMINI_MODEL = model_name="gemini-2.5-flash"

if not api_key:
    print("ERRORE: Variabile di sistema 'GOOGLE_API_KEY' non trovata.")
    sys.exit(1)

# Configura la libreria con la tua API Key
genai.configure(api_key=api_key)

# Definizione del modello Gemini 2.5 Flash
# Le istruzioni di sistema vengono fornite qui per dare contesto all'IA
model = genai.GenerativeModel(
    model_name="gemini-2.5-flash",
    system_instruction=(
        "Sei un generatore di codice puro. "
        "Rispondi SOLO ed ESCLUSIVAMENTE con codice C# valido. "
        "È severamente vietato includere testo discorsivo, saluti o prefazioni. "
        "Non utilizzare i delimitatori di blocco markdown (```csharp). "
        "Il tuo output verrà salvato direttamente in un file .cs, quindi deve essere sintatticamente perfetto."
    )
)

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

# Esempio di come chiamerai il modello nel resto dello script:
# response = model.generate_content("Tuo prompt qui")
# print(response.text)