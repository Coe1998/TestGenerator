import sys
import io
import tree_sitter_c_sharp as csharp
from tree_sitter import Language

# Forza UTF-8 per console Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

CS_LANG = Language(csharp.language())

# ======================================
# MODELLI / PROVIDER
# ======================================

GEMINI_MODEL = "gemini-2.5-flash"
OPENAI_MODEL = "gpt-4o"
OLLAMA_MODEL = "deepseek-coder:6.7b"
OLLAMA_URL   = "http://localhost:11434/api/generate"

# ======================================
# SYSTEM INSTRUCTION (condivisa da tutti i provider)
# ======================================

AI_SYSTEM_INSTRUCTION = (
    "Sei un generatore di codice puro specializzato in Unit Testing C#. "
    "Rispondi SOLO ed ESCLUSIVAMENTE con codice C# valido e compilabile. "
    "È severamente vietato includere testo discorsivo, saluti o prefazioni. "
    "Non utilizzare i delimitatori di blocco markdown (```csharp). "
    "Il tuo output verrà salvato direttamente in un file .cs, quindi deve essere "
    "sintatticamente perfetto. "
    "Usa nomi di metodo descrittivi nel formato: NomeMetodo_Scenario_RisultatoAtteso. "
    "Mocka le dipendenze con Moq se la classe le ha nel costruttore. "
    "Ogni test deve avere i commenti // Arrange / // Act / // Assert."
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
    "ASYNC":       "HIGH",
    "CONSTRUCTOR": "MEDIUM",
    "NULL_SAFETY": "HIGH",
}