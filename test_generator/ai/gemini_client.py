import os
import google.generativeai as genai
from config import GEMINI_MODEL # Es: "gemini-2.5-flash"
from generators.prompt_builder import build_prompt
from core.logger import log_timing

FRAMEWORK_LABELS = {"mstest": "MSTest", "xunit": "xUnit", "nunit": "NUnit"}

def call_gemini(scenarios, source_code, framework="mstest"):
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("GOOGLE_API_KEY non impostata nelle variabili di sistema.")

    genai.configure(api_key=api_key)

    prompt = build_prompt(scenarios, source_code, framework)

    fw_label = FRAMEWORK_LABELS.get(framework.lower(), "MSTest")
    model = genai.GenerativeModel(
        model_name=GEMINI_MODEL,
        system_instruction=f"Sei un esperto di Unit Testing C#. Genera codice {fw_label} e FluentAssertions pulito."
    )

    try:
        with log_timing("ai_call", model=GEMINI_MODEL, framework=framework):
            response = model.generate_content(prompt)
        text = response.text.strip()
        if text.startswith("```"):
            text = "\n".join(text.split("\n")[1:-1])
        return text
    except Exception as e:
        raise RuntimeError(f"Errore durante la generazione con Gemini: {e}")