# Come buildare e distribuire l'installer

## Prerequisiti (solo per chi mantiene il progetto)

| Tool | Versione | Link |
|---|---|---|
| Python | 3.11+ | python.org |
| PyInstaller | 6+ | `pip install pyinstaller` |
| Inno Setup | 6.3+ | jrsoftware.org/isinfo.php |

Le dipendenze Python del progetto devono essere installate nell'ambiente attivo
prima di lanciare PyInstaller:
```
pip install google-generativeai tree-sitter tree-sitter-c-sharp openai pyperclip flask
```

---

## Build in un click

```
installer\build_installer.bat
```

Produce: `installer\dist_installer\TestGeneratorSetup_1.0.exe`

---

## Cosa fa l'installer (per l'utente finale)

1. **Wizard grafico** — nessuna riga di comando, nessuna configurazione manuale
2. **Scelta del provider AI** — Gemini, OpenAI o Ollama
3. **Inserimento API Key** — salvata come variabile di sistema utente (non richiede admin)
4. **Copia dell'eseguibile** — in `%LocalAppData%\TestGenerator\TestGenerator.exe`
5. **Configurazione Visual Studio** — aggiunge automaticamente 3 strumenti in tutti
   i Visual Studio installati sul PC:

   | Strumento | Cosa fa | Come si usa |
   |---|---|---|
   | TestGen - Analizza Classe | Genera test per il file .cs aperto | Apri la classe in VS → Strumenti > TestGen - Analizza Classe |
   | TestGen - Analizza Cartella | Genera test per tutti i .cs nella cartella | Da qualsiasi file nella cartella target |
   | TestGen - Dry Run | Mostra gli scenari senza chiamare l'AI | Anteprima gratuita prima di spendere token |

6. **Uninstaller incluso** — rimuove exe, strumenti VS e (opzionale) API key

---

## Aggiornare la versione

1. Modifica `#define AppVersion` in `installer.iss`
2. Modifica `AppVersion` in `installer.iss` per il nome file output
3. Lancia `build_installer.bat`

---

## Cambiare il nome azienda

Modifica `#define AppPublisher` in `installer.iss`.

---

## Aggiungere il modello Ollama predefinito

Il modello Ollama di default è `deepseek-coder:6.7b` definito in `test_generator/config.py`.
Cambia `OLLAMA_MODEL` prima di buildare se vuoi usare un modello diverso.

---

## Distribuzione

Distribuire solo il file:
```
TestGeneratorSetup_1.0.exe
```
Non richiede Python installato sul PC dell'utente finale.
Non richiede privilegi di amministratore.
