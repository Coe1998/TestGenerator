"""
main.py — TestGenerator entry point
====================================
Modalità disponibili:
  1. CLASSICO   : singolo file .cs  →  main.exe MyClass.cs -g
  2. MULTI-FILE : N file .cs        →  main.exe A.cs B.cs C.cs -g
  3. FOLDER     : cartella          →  main.exe src\Services\ -g [-r]
  4. DASHBOARD  : analytics         →  main.exe --dashboard
"""
import sys
import argparse
import json
from pathlib import Path

from core.logger import init_session, end_session, log_event, log_error, log_timing


# ---------------------------------------------------------------------------
# Rilevamento modalità
# ---------------------------------------------------------------------------

def _detect_mode(inputs: list[str]) -> str:
    """
    Determina la modalità in base agli input:
      'classic'   — esattamente 1 file .cs
      'multifile' — N file .cs specifici (tutti file, nessuna cartella)
      'folder'    — almeno un percorso è una cartella
    """
    paths = [Path(i) for i in inputs]
    if any(p.is_dir() for p in paths):
        return "folder"
    if len(paths) == 1:
        return "classic"
    return "multifile"


# ---------------------------------------------------------------------------
# Raccolta file
# ---------------------------------------------------------------------------

def _collect_cs_files(inputs: list[str], recursive: bool) -> list[Path]:
    """Raccoglie tutti i file .cs validi dagli input (file o cartelle)."""
    file_list = []
    for inp in inputs:
        p = Path(inp)
        if p.is_file() and p.suffix == ".cs" and not p.name.endswith("_Tests.cs"):
            file_list.append(p)
        elif p.is_dir():
            pattern = "**/*.cs" if recursive else "*.cs"
            file_list.extend(
                f for f in p.glob(pattern)
                if not f.name.endswith("_Tests.cs")
                and ".Tests" not in f.parts
            )
    return list(dict.fromkeys(file_list))


# ---------------------------------------------------------------------------
# Workflow per un singolo file
# ---------------------------------------------------------------------------

def analyze(file_path: Path, args, *, call_ai_fn, write_test_file_fn, ai_model) -> tuple[bool, int]:
    """
    Esegue l'intero workflow per un file .cs.
    Restituisce (successo: bool, scenari_trovati: int).
    """
    from analyzers.scenario_generator import ScenarioGenerator

    generator = ScenarioGenerator()
    _file  = file_path.name
    _fpath = str(file_path)

    # 1. ANALISI
    try:
        with log_timing("file_analysis", file=_file, file_path=_fpath):
            all_scenarios, full_content = generator.analyze_source_file(file_path)
    except Exception as e:
        print(f"  [ERRORE] Analisi fallita per {_file}: {e}")
        log_error("file_analysis_failed", exc=e, file=_file, file_path=_fpath)
        return False, 0

    scenario_count = len(all_scenarios)
    log_event("info", "scenarios_found", file=_file, scenarios=scenario_count,
              framework=args.framework, model=ai_model)

    print(f"\n--- ANALISI: {_file} ---")
    print(f"Scenari individuati: {scenario_count}\n")

    # 2. STAMPA RISULTATI
    current_ctx = ""
    for i, s in enumerate(all_scenarios, 1):
        ctx = s.method_context or "Global"
        if ctx != current_ctx:
            print(f"\n  Metodo: {ctx}")
            print("  " + "-" * 30)
            current_ctx = ctx
        print(f"  {i:02d}. [{s.category}] {s.message}")

    # 3. ESPORTAZIONE JSON (opzionale)
    if args.json:
        json_path = file_path.with_name(f"{file_path.stem}_scenarios.json")
        data = [s.to_dict() for s in all_scenarios]
        json_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\n[OK] JSON generato: {json_path.name}")
        log_event("info", "json_exported", file=_file, output_path=str(json_path))

    # 4. CLIPBOARD (opzionale)
    if args.clipboard:
        import pyperclip
        from generators.prompt_builder import build_prompt
        prompt = build_prompt(all_scenarios, full_content, args.framework)
        pyperclip.copy(prompt)
        print("\n[OK] Prompt copiato negli appunti.")
        log_event("info", "clipboard_copy", file=_file)

    # 5. GENERAZIONE TEST (opzionale)
    if args.generate:
        print(f"\n[...] Chiamata a {ai_model} in corso... [framework: {args.framework}]")
        try:
            with log_timing("full_generation", file=_file, framework=args.framework,
                            model=ai_model, scenarios=scenario_count):
                test_code = call_ai_fn(all_scenarios, full_content, args.framework)
                test_path = write_test_file_fn(test_code, str(file_path), args.framework)
            print(f"[OK] Progetto di test creato: {test_path}")
        except Exception as e:
            print(f"[ERRORE] Generazione fallita: {e}")
            return False, scenario_count

    return True, scenario_count


# ---------------------------------------------------------------------------
# Conferma interattiva (modalità multi-file e folder)
# ---------------------------------------------------------------------------

def _ask_confirm(file_list: list[Path], mode: str, framework: str, recursive: bool) -> bool:
    """
    Mostra l'elenco dei file e chiede conferma prima di avviare le chiamate AI.
    Restituisce True se l'utente conferma, False se annulla.
    """
    if mode == "multifile":
        print(f"\nModalità multi-file — {len(file_list)} classi selezionate:")
    else:
        depth = "ricorsiva" if recursive else "solo primo livello"
        print(f"\nModalità cartella ({depth}) — {len(file_list)} classi trovate:")

    for i, f in enumerate(file_list, 1):
        print(f"  {i:02d}. {f}")

    print(f"\nFramework: {framework}")
    print(f"\nStai per generare i test per {len(file_list)} classi "
          f"(una chiamata API per classe). Procedere? [s/N] ", end="", flush=True)

    risposta = input().strip().lower()
    return risposta in ("s", "si", "sì", "y", "yes")


# ---------------------------------------------------------------------------
# CLI & BOOTSTRAP
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="C# Test Generator",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog=(
            "Esempi:\n"
            "  Classico   : main.exe MyClass.cs -g\n"
            "  Multi-file : main.exe A.cs B.cs C.cs -g\n"
            "  Cartella   : main.exe src\\Services\\ -g\n"
            "  Cartella   : main.exe src\\Services\\ -g -r        (ricorsivo)\n"
            "  OpenAI     : main.exe MyClass.cs -g -p openai\n"
            "  Ollama     : main.exe MyClass.cs -g -p ollama\n"
            "  Dry-run    : main.exe src\\Services\\ --dry-run\n"
            "  Dashboard  : main.exe --dashboard\n"
        ),
    )
    parser.add_argument("inputs", nargs="*",
                        help="File .cs (uno o più) oppure una cartella")
    parser.add_argument("--generate",  "-g", action="store_true",
                        help="Genera file .Tests e .csproj tramite AI")
    parser.add_argument("--clipboard", "-c", action="store_true",
                        help="Copia il prompt negli appunti")
    parser.add_argument("--json",      "-j", action="store_true",
                        help="Esporta gli scenari in formato JSON")
    parser.add_argument("--framework", "-f", choices=["mstest", "xunit", "nunit"],
                        default="mstest",
                        help="Framework di test: mstest (default), xunit, nunit")
    parser.add_argument("--recursive", "-r", action="store_true",
                        help="Modalità cartella: scansiona le sottocartelle ricorsivamente")
    parser.add_argument("--provider",  "-p",
                        choices=["gemini", "openai", "ollama"], default="gemini",
                        help="Provider AI: gemini (default), openai, ollama")
    parser.add_argument("--dry-run",   action="store_true",
                        help="Analizza e mostra scenari senza effettuare chiamate AI")
    parser.add_argument("--yes",       "-y", action="store_true",
                        help="Salta la conferma interattiva")
    parser.add_argument("--dashboard", "-d", action="store_true",
                        help="Avvia il dashboard su http://localhost:5050")

    args = parser.parse_args()

    # ── MODALITÀ DASHBOARD ────────────────────────────────────────────────
    if args.dashboard:
        from dashboard.server import run as run_dashboard
        from dashboard.settings import DASHBOARD_PORT
        run_dashboard(port=DASHBOARD_PORT, open_browser=True)
        sys.exit(0)

    # ── DRY-RUN: disabilita la generazione ───────────────────────────────
    if args.dry_run:
        args.generate = False
        print("[DRY-RUN] Nessuna chiamata AI verrà effettuata.\n")

    # ── IMPORT BASE ───────────────────────────────────────────────────────
    import os
    from writers.test_writer import write_test_file
    from config import GEMINI_MODEL, OPENAI_MODEL, OLLAMA_MODEL

    # ── SELEZIONE PROVIDER AI ─────────────────────────────────────────────
    if args.provider == "gemini":
        from ai.gemini_client import call_gemini as call_ai
        ai_model = GEMINI_MODEL
    elif args.provider == "openai":
        from ai.openai_client import call_openai as call_ai
        ai_model = OPENAI_MODEL
    else:  # ollama
        from ai.ollama_client import call_ollama as call_ai
        ai_model = OLLAMA_MODEL

    # ── VALIDAZIONE ANTICIPATA API KEY (solo se --generate) ───────────────
    if args.generate:
        if args.provider == "gemini" and not os.getenv("GOOGLE_API_KEY"):
            print("ERRORE: GOOGLE_API_KEY non impostata. Necessaria per il provider Gemini.")
            sys.exit(1)
        elif args.provider == "openai" and not os.getenv("OPENAI_API_KEY"):
            print("ERRORE: OPENAI_API_KEY non impostata. Necessaria per il provider OpenAI.")
            sys.exit(1)
        # Ollama non richiede API key

    # ── VALIDAZIONE INPUT ─────────────────────────────────────────────────
    if not args.inputs:
        print("Nessun file .cs o cartella specificato.")
        parser.print_help()
        sys.exit(1)

    mode = _detect_mode(args.inputs)

    # ── MODALITÀ 1 — CLASSICO: singolo file .cs ───────────────────────────
    if mode == "classic":
        file_list = _collect_cs_files(args.inputs, recursive=False)
        if not file_list:
            print(f"File non valido o non trovato: {args.inputs[0]}")
            sys.exit(1)

    # ── MODALITÀ 2 — MULTI-FILE: N file .cs specifici ─────────────────────
    elif mode == "multifile":
        file_list = _collect_cs_files(args.inputs, recursive=False)
        if not file_list:
            print("Nessun file .cs valido trovato tra quelli specificati.")
            sys.exit(1)
        if args.generate and not args.yes:
            if not _ask_confirm(file_list, mode, args.framework, args.recursive):
                log_event("info", "multifile_cancelled", total=len(file_list))
                print("Operazione annullata.")
                sys.exit(0)
            log_event("info", "multifile_confirmed", total=len(file_list),
                      framework=args.framework)

    # ── MODALITÀ 3 — FOLDER: cartella con scansione (opz. ricorsiva) ──────
    else:  # mode == "folder"
        file_list = _collect_cs_files(args.inputs, recursive=args.recursive)
        if not file_list:
            depth = "ricorsivamente" if args.recursive else "nel primo livello"
            print(f"Nessun file .cs trovato {depth} nella cartella specificata.")
            sys.exit(1)
        if args.generate and not args.yes:
            if not _ask_confirm(file_list, mode, args.framework, args.recursive):
                log_event("info", "folder_cancelled", total=len(file_list))
                print("Operazione annullata.")
                sys.exit(0)
            log_event("info", "folder_confirmed", total=len(file_list),
                      framework=args.framework)

    # ── SESSIONE ──────────────────────────────────────────────────────────
    is_bulk = len(file_list) > 1
    session_id = init_session(
        framework=args.framework,
        inputs=[str(f) for f in file_list],
        mode=mode,
        provider=args.provider,
        recursive=args.recursive,
        bulk=is_bulk,
        generate=args.generate,
        model=ai_model,
    )

    # ── ELABORAZIONE ──────────────────────────────────────────────────────
    print(f"\nProcessando {len(file_list)} file...")
    ok_count        = 0
    fail_count      = 0
    total_scenarios = 0

    for i, f in enumerate(file_list, 1):
        if is_bulk:
            print(f"\n[{i}/{len(file_list)}] {f.name}")
        success, n_scenarios = analyze(
            f, args,
            call_ai_fn=call_ai,
            write_test_file_fn=write_test_file,
            ai_model=ai_model,
        )
        total_scenarios += n_scenarios
        if success:
            ok_count += 1
        else:
            fail_count += 1

    # ── RIEPILOGO ─────────────────────────────────────────────────────────
    end_session(ok_count, fail_count)

    if is_bulk:
        print("\n" + "=" * 40)
        print(f"RIEPILOGO: {ok_count} completati, {fail_count} errori su {len(file_list)} file.")
        print("=" * 40)

    # ── REPORTING CENTRALE (best-effort, silenzioso) ───────────────────────
    try:
        from core.reporter import report_session
        from core.logger import _logger
        report_session(
            session_id=session_id,
            framework=args.framework,
            model=ai_model,
            total_files=len(file_list),
            ok_count=ok_count,
            fail_count=fail_count,
            total_scenarios=total_scenarios,
            total_ai_ms=0,
            bulk=is_bulk,
        )
    except Exception:
        pass  # Mai bloccare per via del reporting
