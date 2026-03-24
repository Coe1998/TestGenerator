import os
import time
import google.generativeai as genai
from config import GEMINI_MODEL, AI_SYSTEM_INSTRUCTION
from generators.prompt_builder import build_prompt
from core.logger import log_timing, log_event

_MAX_RETRIES   = 3
_RETRY_DELAY_S = 2


def call_gemini(scenarios, source_code, framework="mstest"):
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("GOOGLE_API_KEY non impostata nelle variabili di sistema.")

    genai.configure(api_key=api_key)
    prompt = build_prompt(scenarios, source_code, framework)
    model = genai.GenerativeModel(
        model_name=GEMINI_MODEL,
        system_instruction=AI_SYSTEM_INSTRUCTION,
    )

    last_exc = None
    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            with log_timing("ai_call", model=GEMINI_MODEL, framework=framework, attempt=attempt):
                response = model.generate_content(prompt)
            text = response.text.strip()
            if text.startswith("```"):
                text = "\n".join(text.split("\n")[1:-1])
            return text
        except Exception as e:
            last_exc = e
            if attempt < _MAX_RETRIES:
                delay = _RETRY_DELAY_S * attempt
                log_event("warning", "ai_retry",
                          model=GEMINI_MODEL, attempt=attempt, error=str(e))
                print(f"  [WARN] Tentativo {attempt}/{_MAX_RETRIES} fallito, "
                      f"riprovo tra {delay}s... ({e})")
                time.sleep(delay)

    raise RuntimeError(f"Errore Gemini dopo {_MAX_RETRIES} tentativi: {last_exc}")