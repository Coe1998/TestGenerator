import os
import subprocess
import re
from pathlib import Path
from core.logger import log_timing, log_event, log_error

def get_installed_nuget_version(package_name, fallback_version):
    """
    Controlla nella cache globale di NuGet (~/.nuget/packages) 
    la versione più recente installata per un pacchetto.
    """
    try:
        # NuGet salva le cartelle dei pacchetti in minuscolo
        nuget_path = Path(os.environ.get('USERPROFILE', os.path.expanduser("~"))) / ".nuget" / "packages" / package_name.lower()
        
        if not nuget_path.exists():
            return fallback_version
        
        # Recupera tutte le sottocartelle (versioni) e le ordina
        versions = [d.name for d in nuget_path.iterdir() if d.is_dir()]
        
        if not versions:
            return fallback_version
            
        # Ordinamento semplice (per versioni semantiche complesse servirebbe packaging.version, 
        # ma per un uso standard l'ordinamento di lista è sufficiente)
        versions.sort()
        return versions[-1]
    except Exception:
        return fallback_version

def get_target_framework(csproj_path):
    """Estrae il TargetFramework dal file .csproj originale."""
    try:
        with open(csproj_path, "r", encoding="utf-8") as f:
            content = f.read()
            match = re.search(r"<TargetFramework>(.*?)</TargetFramework>", content)
            if match:
                return match.group(1)
    except Exception:
        pass
    return "net8.0"

FRAMEWORK_PACKAGES = {
    "mstest": {
        "FluentAssertions": "6.12.0",
        "Microsoft.NET.Test.Sdk": "17.8.0",
        "Moq": "4.20.70",
        "MSTest.TestAdapter": "3.1.1",
        "MSTest.TestFramework": "3.1.1",
    },
    "xunit": {
        "FluentAssertions": "6.12.0",
        "Microsoft.NET.Test.Sdk": "17.8.0",
        "Moq": "4.20.70",
        "xunit": "2.6.6",
        "xunit.runner.visualstudio": "2.5.8",
    },
    "nunit": {
        "FluentAssertions": "6.12.0",
        "Microsoft.NET.Test.Sdk": "17.8.0",
        "Moq": "4.20.70",
        "NUnit": "4.1.0",
        "NUnit3TestAdapter": "4.5.0",
    },
}

def write_test_file(test_code, source_path, framework="mstest"):
    """
    Versione definitiva: rileva il Framework e le versioni NuGet 
    direttamente dal sistema dell'utente.
    """
    
    # 1. Pulizia Codice
    if test_code.startswith("```"):
        lines = test_code.splitlines()
        test_code = "\n".join(
            line for line in lines
            if not line.strip().startswith("```")
        ).strip()

    # 2. Percorsi
    source_file = Path(source_path).resolve()
    project_name = f"{source_file.stem}.Tests"
    # Saliamo di un livello per creare la cartella test parallela alla cartella sorgente
    base_dir = source_file.parent.parent if len(source_file.parents) > 1 else source_file.parent
    test_project_dir = base_dir / project_name
    test_project_dir.mkdir(parents=True, exist_ok=True)

    test_file_path = test_project_dir / f"{source_file.stem}Tests.cs"
    csproj_path = test_project_dir / f"{project_name}.csproj"

    # 3. Ricerca Progetto Originale e Detection Framework
    original_csproj = None
    search_ptr = source_file.parent
    for _ in range(3):
        matches = list(search_ptr.glob("*.csproj"))
        matches = [m for m in matches if m.resolve() != csproj_path.resolve()]
        if matches:
            original_csproj = matches[0]
            break
        search_ptr = search_ptr.parent

    target_framework = "net8.0"
    project_ref_xml = ""
    
    if original_csproj:
        target_framework = get_target_framework(original_csproj)
        rel_path = os.path.relpath(original_csproj, test_project_dir)
        project_ref_xml = f"""
  <ItemGroup>
    <ProjectReference Include="{rel_path}" />
  </ItemGroup>"""

    # 4. Rilevamento Versioni NuGet (Dinamico)
    # Definiamo i pacchetti necessari in base al framework scelto
    default_packages = FRAMEWORK_PACKAGES.get(framework.lower(), FRAMEWORK_PACKAGES["mstest"])
    
    # Generiamo i tag <PackageReference> usando le versioni trovate sul PC
    package_refs = []
    for pkg, fallback in default_packages.items():
        v = get_installed_nuget_version(pkg, fallback)
        package_refs.append(f'    <PackageReference Include="{pkg}" Version="{v}" />')
    
    package_refs_xml = "\n".join(package_refs)

    # 5. Generazione Template .csproj
    csproj_content = f"""<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <TargetFramework>{target_framework}</TargetFramework>
    <ImplicitUsings>enable</ImplicitUsings>
    <Nullable>enable</Nullable>
    <IsPackable>false</IsPackable>
  </PropertyGroup>

  <ItemGroup>
{package_refs_xml}
  </ItemGroup>
{project_ref_xml}
</Project>"""

    # 6. Scrittura File
    with log_timing("test_write", file=source_file.name, output_path=str(test_file_path),
                    framework=framework):
        with open(csproj_path, "w", encoding="utf-8") as f:
            f.write(csproj_content)
        with open(test_file_path, "w", encoding="utf-8") as f:
            f.write(test_code)

    # 7. Ricerca e aggiornamento Solution (.slnx o .sln)
    sln_file = None
    current_search_dir = source_file.parent
    while current_search_dir != current_search_dir.parent:
        sln_matches = list(current_search_dir.glob("*.slnx")) + list(current_search_dir.glob("*.sln"))
        if sln_matches:
            sln_file = sln_matches[0]
            break
        current_search_dir = current_search_dir.parent

    if sln_file:
        try:
            with log_timing("sln_update", file=source_file.name, output_path=str(sln_file)):
                subprocess.run(
                    ["dotnet", "sln", str(sln_file), "add", str(csproj_path)],
                    check=True, capture_output=True, text=True
                )
            print(f"[OK] Solution '{sln_file.name}' aggiornata (Framework: {target_framework})")
        except subprocess.CalledProcessError as e:
            err = e.stderr.strip()
            print(f"[WARN] Impossibile aggiungere alla solution: {err}")
            log_error("sln_update_failed", file=source_file.name,
                      output_path=str(sln_file), error=err)
    else:
        log_event("warning", "sln_not_found", file=source_file.name)

    return str(test_file_path)