<#
.SYNOPSIS
    Installa o rimuove gli strumenti esterni TestGenerator in tutte le istanze
    di Visual Studio trovate nel registro dell'utente corrente.

.PARAMETER Mode
    "install" (default) oppure "uninstall"

.PARAMETER ExePath
    Percorso completo all'eseguibile TestGenerator.exe

.PARAMETER ProviderIdx
    0 = Gemini (default)  |  1 = OpenAI  |  2 = Ollama
#>

param(
    [string] $Mode        = "install",
    [string] $ExePath     = "",
    [int]    $ProviderIdx = 0
)

# ---------------------------------------------------------------------------
# Costanti
# ---------------------------------------------------------------------------

$ToolPrefix   = "TestGen"          # Usato per riconoscere i tool al momento dell'uninstall
$VsRegBase    = "HKCU:\Software\Microsoft\VisualStudio"

# ToolOpt flags di Visual Studio:
#   0x01 = Prompt arguments  |  0x02 = Use output window
#   0x04 = Treat as Unicode  |  0x10 = Close on exit
$ToolOpt = 18   # 0x02 (output window) + 0x10 (close on exit)

# Argomento provider da appendere a --generate
$ProviderArgs = @("", " --provider openai", " --provider ollama")
$ProviderFlag = $ProviderArgs[$ProviderIdx]

# 3 strumenti da installare
$Tools = @(
    [PSCustomObject]@{
        Title = "TestGen - Analizza Classe"
        Args  = "`$(ItemPath) --generate$ProviderFlag"
        Dir   = "`$(ItemDir)"
    },
    [PSCustomObject]@{
        Title = "TestGen - Analizza Cartella"
        Args  = "`$(ItemDir) --generate$ProviderFlag"
        Dir   = "`$(ItemDir)"
    },
    [PSCustomObject]@{
        Title = "TestGen - Dry Run (anteprima scenari)"
        Args  = "`$(ItemPath) --dry-run"
        Dir   = "`$(ItemDir)"
    }
)

# ---------------------------------------------------------------------------
# Funzioni helper
# ---------------------------------------------------------------------------

function Get-VsInstances {
    if (-not (Test-Path $VsRegBase)) { return @() }
    Get-ChildItem $VsRegBase -ErrorAction SilentlyContinue |
        Where-Object { $_.PSChildName -match '^\d+\.\d+_' }
}

function Get-ExternalToolsKey([string]$InstancePath) {
    $key = "$InstancePath\External Tools"
    if (Test-Path $key) { return $key }
    return $null
}

function Get-ToolCount([string]$KeyPath) {
    $p = Get-ItemProperty $KeyPath -ErrorAction SilentlyContinue
    if ($null -eq $p -or $null -eq $p.ToolCount) { return 0 }
    return [int]$p.ToolCount
}

function Test-AlreadyInstalled([string]$KeyPath, [string]$ExePath) {
    $count = Get-ToolCount $KeyPath
    for ($i = 0; $i -lt $count; $i++) {
        $cmd   = (Get-ItemProperty $KeyPath -Name "ToolCmd$i"   -ErrorAction SilentlyContinue)."ToolCmd$i"
        $title = (Get-ItemProperty $KeyPath -Name "ToolTitle$i" -ErrorAction SilentlyContinue)."ToolTitle$i"
        if ($cmd -eq $ExePath -and $title -like "$ToolPrefix*") {
            return $true
        }
    }
    return $false
}

# ---------------------------------------------------------------------------
# INSTALL
# ---------------------------------------------------------------------------

function Install-Tools {
    if ([string]::IsNullOrWhiteSpace($ExePath)) {
        Write-Error "ExePath non specificato."
        exit 1
    }
    if (-not (Test-Path $ExePath)) {
        Write-Warning "Exe non trovato al percorso: $ExePath"
    }

    $instances = Get-VsInstances
    if ($instances.Count -eq 0) {
        Write-Host "Nessuna istanza di Visual Studio trovata. Strumenti VS non configurati."
        exit 0
    }

    $installed = 0
    foreach ($instance in $instances) {
        $keyPath = Get-ExternalToolsKey $instance.PSPath
        if (-not $keyPath) {
            Write-Host "  [SKIP] $($instance.PSChildName): chiave 'External Tools' non trovata."
            continue
        }

        if (Test-AlreadyInstalled $keyPath $ExePath) {
            Write-Host "  [SKIP] $($instance.PSChildName): strumenti gia' presenti."
            continue
        }

        $count = Get-ToolCount $keyPath

        foreach ($tool in $Tools) {
            Set-ItemProperty $keyPath -Name "ToolTitle$count" -Value $tool.Title
            Set-ItemProperty $keyPath -Name "ToolCmd$count"   -Value $ExePath
            Set-ItemProperty $keyPath -Name "ToolArg$count"   -Value $tool.Args
            Set-ItemProperty $keyPath -Name "ToolDir$count"   -Value $tool.Dir
            Set-ItemProperty $keyPath -Name "ToolOpt$count"   -Value $ToolOpt
            $count++
        }

        Set-ItemProperty $keyPath -Name "ToolCount" -Value $count
        Write-Host "  [OK]   $($instance.PSChildName): $($Tools.Count) strumenti aggiunti."
        $installed++
    }

    if ($installed -gt 0) {
        Write-Host ""
        Write-Host "Strumenti installati in $installed istanza/e di Visual Studio."
        Write-Host "Riavvia Visual Studio per visualizzare i nuovi strumenti in Strumenti > Strumenti esterni."
    }
}

# ---------------------------------------------------------------------------
# UNINSTALL
# ---------------------------------------------------------------------------

function Uninstall-Tools {
    $instances = Get-VsInstances
    if ($instances.Count -eq 0) { return }

    foreach ($instance in $instances) {
        $keyPath = Get-ExternalToolsKey $instance.PSPath
        if (-not $keyPath) { continue }

        $count = Get-ToolCount $keyPath
        if ($count -eq 0) { continue }

        # Raccoglie gli indici da rimuovere
        $toRemove = @()
        for ($i = 0; $i -lt $count; $i++) {
            $title = (Get-ItemProperty $keyPath -Name "ToolTitle$i" -ErrorAction SilentlyContinue)."ToolTitle$i"
            $cmd   = (Get-ItemProperty $keyPath -Name "ToolCmd$i"   -ErrorAction SilentlyContinue)."ToolCmd$i"
            if ($title -like "$ToolPrefix*" -or $cmd -like "*TestGenerator*") {
                $toRemove += $i
            }
        }

        if ($toRemove.Count -eq 0) { continue }

        # Ricostruisce l'elenco senza i tool rimossi
        $remaining = @()
        for ($i = 0; $i -lt $count; $i++) {
            if ($toRemove -notcontains $i) {
                $remaining += [PSCustomObject]@{
                    Title = (Get-ItemProperty $keyPath -Name "ToolTitle$i")."ToolTitle$i"
                    Cmd   = (Get-ItemProperty $keyPath -Name "ToolCmd$i")."ToolCmd$i"
                    Arg   = (Get-ItemProperty $keyPath -Name "ToolArg$i")."ToolArg$i"
                    Dir   = (Get-ItemProperty $keyPath -Name "ToolDir$i")."ToolDir$i"
                    Opt   = (Get-ItemProperty $keyPath -Name "ToolOpt$i")."ToolOpt$i"
                }
            }
        }

        # Cancella tutte le voci esistenti
        for ($i = 0; $i -lt $count; $i++) {
            Remove-ItemProperty $keyPath -Name "ToolTitle$i" -ErrorAction SilentlyContinue
            Remove-ItemProperty $keyPath -Name "ToolCmd$i"   -ErrorAction SilentlyContinue
            Remove-ItemProperty $keyPath -Name "ToolArg$i"   -ErrorAction SilentlyContinue
            Remove-ItemProperty $keyPath -Name "ToolDir$i"   -ErrorAction SilentlyContinue
            Remove-ItemProperty $keyPath -Name "ToolOpt$i"   -ErrorAction SilentlyContinue
        }

        # Riscrive solo i tool rimasti
        for ($i = 0; $i -lt $remaining.Count; $i++) {
            Set-ItemProperty $keyPath -Name "ToolTitle$i" -Value $remaining[$i].Title
            Set-ItemProperty $keyPath -Name "ToolCmd$i"   -Value $remaining[$i].Cmd
            Set-ItemProperty $keyPath -Name "ToolArg$i"   -Value $remaining[$i].Arg
            Set-ItemProperty $keyPath -Name "ToolDir$i"   -Value $remaining[$i].Dir
            Set-ItemProperty $keyPath -Name "ToolOpt$i"   -Value $remaining[$i].Opt
        }

        Set-ItemProperty $keyPath -Name "ToolCount" -Value $remaining.Count
        Write-Host "  [OK] $($instance.PSChildName): $($toRemove.Count) strumento/i rimosso/i."
    }
}

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

Write-Host ""
Write-Host "=== TestGenerator VS Tools Setup (modalita': $Mode) ==="
Write-Host ""

switch ($Mode.ToLower()) {
    "install"   { Install-Tools }
    "uninstall" { Uninstall-Tools }
    default     { Write-Error "Modalita' non valida. Usa 'install' o 'uninstall'." ; exit 1 }
}

Write-Host ""
exit 0
