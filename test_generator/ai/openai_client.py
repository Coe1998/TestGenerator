import os
import time
from openai import OpenAI
from config import OPENAI_MODEL, AI_SYSTEM_INSTRUCTION
from generators.prompt_builder import build_prompt
from core.logger import log_timing, log_event

_MAX_RETRIES   = 3
_RETRY_DELAY_S = 2


def call_openai(scenarios, source_code: str, framework: str = "mstest") -> str:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY non impostata nelle variabili di sistema.")

    client = OpenAI(api_key=api_key)
    prompt = build_prompt(scenarios, source_code, framework)

    last_exc = None
    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            with log_timing("ai_call", model=OPENAI_MODEL, framework=framework, attempt=attempt):
                response = client.chat.completions.create(
                    model=OPENAI_MODEL,
                    messages=[
                        {"role": "system", "content": AI_SYSTEM_INSTRUCTION},
                        {"role": "user",   "content": prompt},
                    ],
                )
            text = response.choices[0].message.content.strip()
            if text.startswith("```"):
                text = "\n".join(text.split("\n")[1:-1])
            return text
        except Exception as e:
            last_exc = e
            if attempt < _MAX_RETRIES:
                delay = _RETRY_DELAY_S * attempt
                log_event("warning", "ai_retry",
                          model=OPENAI_MODEL, attempt=attempt, error=str(e))
                print(f"  [WARN] Tentativo {attempt}/{_MAX_RETRIES} fallito, "
                      f"riprovo tra {delay}s... ({e})")
                time.sleep(delay)

    raise RuntimeError(f"Errore OpenAI dopo {_MAX_RETRIES} tentativi: {last_exc}")