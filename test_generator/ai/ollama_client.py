import json
import urllib.request
import urllib.error

from config import OLLAMA_MODEL, OLLAMA_URL
from generators.prompt_builder import build_prompt


FRAMEWORK_SYNTAX = {
    "mstest": "MSTest ([TestClass], [TestMethod], [TestInitialize])",
    "xunit":  "xUnit ([Fact], [Theory], costruttore per setup, IDisposable per teardown)",
    "nunit":  "NUnit ([TestFixture], [Test], [SetUp], [TearDown])",
}

def _build_system_prompt(framework="mstest"):
    fw_syntax = FRAMEWORK_SYNTAX.get(framework.lower(), FRAMEWORK_SYNTAX["mstest"])
    return f"""Sei un esperto di unit testing in C#.
Il tuo compito è generare una classe di test completa e compilabile.

Regole TASSATIVE:
- Usa SOLO {fw_syntax} e FluentAssertions (.Should())
- Restituisci ESCLUSIVAMENTE codice C# puro, senza blocchi markdown, senza ```, senza spiegazioni
- La prima riga deve essere un using o il namespace, mai testo libero
- Usa nomi di metodo descrittivi nel formato: NomeMetodo_Scenario_RisultatoAtteso
- Mocka le dipendenze con Moq se la classe le ha nel costruttore
- Ogni test deve avere i commenti // Arrange / // Act / // Assert"""


def call_ollama(scenarios, class_content, framework="mstest"):
    user_prompt = build_prompt(scenarios, class_content, framework)
    full_prompt = _build_system_prompt(framework) + "\n\n" + user_prompt

    payload = json.dumps({
        "model": OLLAMA_MODEL,
        "prompt": full_prompt,
        "stream": False
    }).encode("utf-8")

    req = urllib.request.Request(
        OLLAMA_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            result = json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as e:
        raise RuntimeError(f"Errore connessione Ollama: {e.reason}") from e

    return result["response"].strip()