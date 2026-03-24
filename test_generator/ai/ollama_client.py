import json
import time
import urllib.request
import urllib.error

from config import OLLAMA_MODEL, OLLAMA_URL, AI_SYSTEM_INSTRUCTION
from generators.prompt_builder import build_prompt
from core.logger import log_timing, log_event

_MAX_RETRIES   = 3
_RETRY_DELAY_S = 2

FRAMEWORK_SYNTAX = {
    "mstest": "MSTest ([TestClass], [TestMethod], [TestInitialize])",
    "xunit":  "xUnit ([Fact], [Theory], costruttore per setup, IDisposable per teardown)",
    "nunit":  "NUnit ([TestFixture], [Test], [SetUp], [TearDown])",
}


def _build_system_prompt(framework="mstest"):
    fw_syntax = FRAMEWORK_SYNTAX.get(framework.lower(), FRAMEWORK_SYNTAX["mstest"])
    return (
        AI_SYSTEM_INSTRUCTION + "\n\n"
        f"Framework richiesto: {fw_syntax} e FluentAssertions (.Should())."
    )


def call_ollama(scenarios, class_content, framework="mstest"):
    user_prompt  = build_prompt(scenarios, class_content, framework)
    full_prompt  = _build_system_prompt(framework) + "\n\n" + user_prompt

    payload = json.dumps({
        "model":  OLLAMA_MODEL,
        "prompt": full_prompt,
        "stream": False,
    }).encode("utf-8")

    req = urllib.request.Request(
        OLLAMA_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    last_exc = None
    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            with log_timing("ai_call", model=OLLAMA_MODEL, framework=framework, attempt=attempt):
                with urllib.request.urlopen(req, timeout=300) as resp:
                    result = json.loads(resp.read().decode("utf-8"))
            return result["response"].strip()
        except urllib.error.URLError as e:
            last_exc = e
            if attempt < _MAX_RETRIES:
                delay = _RETRY_DELAY_S * attempt
                log_event("warning", "ai_retry",
                          model=OLLAMA_MODEL, attempt=attempt, error=str(e))
                print(f"  [WARN] Tentativo {attempt}/{_MAX_RETRIES} fallito, "
                      f"riprovo tra {delay}s... ({e.reason})")
                time.sleep(delay)
        except Exception as e:
            last_exc = e
            if attempt < _MAX_RETRIES:
                delay = _RETRY_DELAY_S * attempt
                log_event("warning", "ai_retry",
                          model=OLLAMA_MODEL, attempt=attempt, error=str(e))
                print(f"  [WARN] Tentativo {attempt}/{_MAX_RETRIES} fallito, "
                      f"riprovo tra {delay}s... ({e})")
                time.sleep(delay)

    raise RuntimeError(f"Errore Ollama dopo {_MAX_RETRIES} tentativi: {last_exc}")