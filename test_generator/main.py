"""
main.py — TestGenerator entry point
====================================
Modalità disponibili:
  1. Analisi / generazione test (default)
  2. Dashboard analytics  →  main.exe --dashboard
"""
import sys
import argparse
import json
from pathlib import Path

# Logger: non dipende da config.py, sicuro da importare subito
from core.logger import init_session, end_session, log_event, log_error, log_timing


# ---------------------------------------------------------------------------
# Workflow per un singolo file
# ---------------------------------------------------------------------------

def analyze(file_path: Path, args, *, call_gemini_fn, write_test_file_fn, gemini_model) -> tuple[bool, int]:
    """
    Esegue l'intero workflow per un file .cs.
    Restituisce (successo: bool, scenari_trovati: int).
    """
    # Import locale → non dipende da config.py finché non si entra qui
    from analyzers.scenario_generator import ScenarioGenerator

    generator = ScenarioGenerator()
    _file  = file_path.name
    _fpath = str(file_path)

    # 1. ANALISI E RISOLUZIONE
    try:
        with log_timing("file_analysis", file=_file, file_path=_fpath):
            all_scenarios, full_content = generator.analyze_source_file(file_path)
    except Exception as e:
        print(f"  [ERRORE] Analisi fallita per {_file}: {e}")
        log_error("file_analysis_failed", exc=e, file=_file, file_path=_fpath)
        return False, 0

    scenario_count = len(all_scenarios)
    log_event("info", "scenarios_found", file=_file, scenarios=scenario_count,
              framework=args.framework)

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
        print(f"\n[...] Chiamata a Gemini ({gemini_model}) in corso... [framework: {args.framework}]")
        try:
            with log_timing("full_generation", file=_file, framework=args.framework,
                            model=gemini_model, scenarios=scenario_count):
                test_code = call_gemini_fn(all_scenarios, full_content, args.framework)
                test_path = write_test_file_fn(test_code, str(file_path), args.framework)
            print(f"[OK] Progetto di test creato: {test_path}")
        except Exception as e:
            print(f"[ERRORE] Generazione fallita: {e}")
            return False, scenario_count

    return True, scenario_count


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
# CLI & BOOTSTRAP
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="C# Scenario Generator & Test Writer")
    parser.add_argument("inputs", nargs="*", help="File .cs o cartelle da analizzare")
    parser.add_argument("--generate",  "-g", action="store_true", help="Genera file .Tests e .csproj")
    parser.add_argument("--clipboard", "-c", action="store_true", help="Copia il prompt negli appunti")
    parser.add_argument("--json",      "-j", action="store_true", help="Esporta gli scenari in formato JSON")
    parser.add_argument("--framework", "-f", choices=["mstest", "xunit", "nunit"], default="mstest",
                        help="Framework di test: mstest (default), xunit, nunit")
    parser.add_argument("--recursive", "-r", action="store_true",
                        help="Scansiona le sottocartelle ricorsivamente (modalità bulk)")
    parser.add_argument("--yes",       "-y", action="store_true",
                        help="Salta la conferma interattiva in modalità bulk")
    parser.add_argument("--dashboard", "-d", action="store_true",
                        help="Avvia il dashboard di analisi su http://localhost:5050")

    args = parser.parse_args()

    # ── MODALITÀ DASHBOARD ────────────────────────────────────────────────
    # Gestita subito, prima di qualsiasi import che richieda l'API key.
    if args.dashboard:
        from dashboard.server import run as run_dashboard
        from dashboard.settings import DASHBOARD_PORT
        run_dashboard(port=DASHBOARD_PORT, open_browser=True)
        sys.exit(0)

    # ── IMPORT PESANTI (richiedono GOOGLE_API_KEY) ────────────────────────
    from ai.gemini_client import call_gemini
    from writers.test_writer import write_test_file
    from config import GEMINI_MODEL

    # ── RACCOLTA FILE ─────────────────────────────────────────────────────
    if not args.inputs:
        print("Nessun file .cs o cartella specificato.")
        parser.print_help()
        sys.exit(1)

    file_list = _collect_cs_files(args.inputs, args.recursive)

    if not file_list:
        print("Nessun file .cs valido trovato.")
        sys.exit(1)

    is_bulk  = len(file_list) > 1
    session_id = init_session(
        framework=args.framework,
        inputs=[str(f) for f in file_list],
        recursive=args.recursive,
        bulk=is_bulk,
        generate=args.generate,
        model=GEMINI_MODEL,
    )

    # ── CONFERMA BULK ─────────────────────────────────────────────────────
    if args.generate and is_bulk and not args.yes:
        print(f"\nModalità bulk — verranno generate chiamate AI per {len(file_list)} classi:\n")
        for i, f in enumerate(file_list, 1):
            print(f"  {i:02d}. {f}")
        print(f"\nFramework: {args.framework}")
        print("\nProcedere? Verrà effettuata UNA chiamata API per ogni classe. [s/N] ", end="", flush=True)
        risposta = input().strip().lower()
        if risposta not in ("s", "si", "sì", "y", "yes"):
            log_event("info", "bulk_cancelled", total=len(file_list))
            print("Operazione annullata.")
            sys.exit(0)
        log_event("info", "bulk_confirmed", total=len(file_list), framework=args.framework)

    # ── ELABORAZIONE ──────────────────────────────────────────────────────
    print(f"\nProcessando {len(file_list)} file...")
    ok_count       = 0
    fail_count     = 0
    total_scenarios = 0

    for i, f in enumerate(file_list, 1):
        if is_bulk:
            print(f"\n[{i}/{len(file_list)}] {f.name}")
        success, n_scenarios = analyze(
            f, args,
            call_gemini_fn=call_gemini,
            write_test_file_fn=write_test_file,
            gemini_model=GEMINI_MODEL,
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
        # Calcola ms AI totali dai log dell'ultima sessione
        # (approssimazione: raccogliamo dall'ultimo log tramite logger state)
        from core.logger import _logger
        report_session(
            session_id=session_id,
            framework=args.framework,
            model=GEMINI_MODEL,
            total_files=len(file_list),
            ok_count=ok_count,
            fail_count=fail_count,
            total_scenarios=total_scenarios,
            total_ai_ms=0,    # Il totale AI ms preciso è nel log; 0 se non calcolato
            bulk=is_bulk,
        )
    except Exception:
        pass  # Mai bloccare per via del reporting
