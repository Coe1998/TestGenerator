import sys
import io
import tree_sitter_c_sharp as csharp
from tree_sitter import Language

# Forza UTF-8 per console Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

CS_LANG = Language(csharp.language())

# ======================================
# CONFIGURAZIONE OLLAMA
# ======================================

OLLAMA_MODEL = "deepseek-coder:6.7b"
OLLAMA_URL = "http://localhost:11434/api/generate"

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