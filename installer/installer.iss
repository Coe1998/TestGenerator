; =============================================================================
; TestGenerator — Installer
; Requires: Inno Setup 6.3+ (https://jrsoftware.org/isinfo.php)
;
; Come buildare:
;   1. Esegui build_installer.bat  OPPURE
;   2. Apri questo file in Inno Setup e premi Ctrl+F9
; =============================================================================

#define AppName      "TestGenerator"
#define AppVersion   "1.0"
#define AppPublisher "La tua azienda"
#define AppExeName   "TestGenerator.exe"
#define AppExeSrc    "..\test_generator\dist\TestGenerator.exe"
#define PsScript     "setup_vs_tools.ps1"

; ---------------------------------------------------------------------------
[Setup]
; GUID univoco per questa applicazione — NON cambiare dopo la prima release
AppId={{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL=
VersionInfoVersion={#AppVersion}

; Installazione per-utente (no UAC, no admin)
DefaultDirName={localappdata}\{#AppName}
DefaultGroupName={#AppName}
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

; Output
OutputDir=dist_installer
OutputBaseFilename=TestGeneratorSetup_{#AppVersion}

; UI
WizardStyle=modern
WizardSizePercent=120
SetupIconFile=
DisableWelcomePage=no
DisableDirPage=yes
DisableProgramGroupPage=yes
ShowLanguageDialog=no

; Compressione
Compression=lzma2/ultra
SolidCompression=yes
InternalCompressLevel=ultra

; ---------------------------------------------------------------------------
[Languages]
Name: "it"; MessagesFile: "compiler:Languages\Italian.isl"

; ---------------------------------------------------------------------------
[Messages]
; Personalizzazione testi wizard
WelcomeLabel1=Benvenuto nel programma di installazione di {#AppName}
WelcomeLabel2=Questo programma installera' {#AppName} sul tuo computer.%n%nVerra' configurato automaticamente:%n  - Eseguibile TestGenerator.exe%n  - Strumenti esterni in Visual Studio%n  - Variabile di sistema per la API Key%n%nPrima di continuare assicurati che Visual Studio sia CHIUSO.
FinishedHeadingLabel=Installazione completata
FinishedLabel=L''installazione di {#AppName} e' stata completata.%n%nRiavvia Visual Studio: i nuovi strumenti compariranno nel menu Strumenti > Strumenti Esterni.

; ---------------------------------------------------------------------------
[Files]
; Eseguibile principale
Source: "{#AppExeSrc}";  DestDir: "{app}"; Flags: ignoreversion

; Script PowerShell (viene eliminato dopo l'esecuzione)
Source: "{#PsScript}";   DestDir: "{app}"; Flags: ignoreversion deleteafterinstall

; ---------------------------------------------------------------------------
[Icons]
Name: "{group}\{#AppName}";              Filename: "{app}\{#AppExeName}"
Name: "{group}\Disinstalla {#AppName}";  Filename: "{uninstallexe}"

; ---------------------------------------------------------------------------
[Code]

var
  ProviderPage : TInputOptionWizardPage;
  ApiKeyPage   : TInputQueryWizardPage;

// ---------------------------------------------------------------------------
// Creazione pagine custom del wizard
// ---------------------------------------------------------------------------

procedure InitializeWizard;
begin
  // --- Pagina 1: scelta provider AI ---
  ProviderPage := CreateInputOptionPage(
    wpWelcome,
    'Provider AI',
    'Seleziona il provider AI che vuoi usare',
    'Il provider e'' il servizio che genera i test. Puoi cambiarlo in seguito ' +
    'tramite le variabili di sistema del tuo PC.',
    True,   // Exclusive (radio buttons)
    False   // ListBox
  );
  ProviderPage.Add('Gemini Flash  (Google)  —  richiede variabile GOOGLE_API_KEY');
  ProviderPage.Add('GPT-4o        (OpenAI)  —  richiede variabile OPENAI_API_KEY');
  ProviderPage.Add('Ollama        (locale)  —  nessuna API key, modello su questo PC');
  ProviderPage.Values[0] := True; // default: Gemini

  // --- Pagina 2: inserimento API key ---
  ApiKeyPage := CreateInputQueryPage(
    ProviderPage.ID,
    'API Key',
    'Inserisci la tua API Key',
    'La chiave verra'' salvata come variabile di sistema per il tuo utente Windows.' + #13#10 +
    'Non verra'' mai trasmessa ad altri sistemi oltre al provider scelto.' + #13#10 +
    'Se selezioni Ollama questa pagina viene saltata automaticamente.',
    False  // non e' una pagina password (il controllo singolo sotto e' mascherato)
  );
  ApiKeyPage.Add('API Key:', True);  // True = campo mascherato (caratteri nascosti)
end;

// ---------------------------------------------------------------------------
// Salta la pagina API key se l'utente sceglie Ollama
// ---------------------------------------------------------------------------

function ShouldSkipPage(PageID: Integer): Boolean;
begin
  Result := False;
  if PageID = ApiKeyPage.ID then
    Result := ProviderPage.Values[2]; // True = Ollama selezionato -> salta
end;

// ---------------------------------------------------------------------------
// Validazione: se non Ollama, la key non puo' essere vuota
// ---------------------------------------------------------------------------

function NextButtonClick(CurPageID: Integer): Boolean;
var
  Key : String;
begin
  Result := True;

  if CurPageID = ApiKeyPage.ID then
  begin
    Key := Trim(ApiKeyPage.Values[0]);
    if Key = '' then
    begin
      MsgBox(
        'La API Key non puo'' essere vuota.' + #13#10 +
        'Inserisci la chiave oppure torna indietro e seleziona Ollama.',
        mbError, MB_OK
      );
      Result := False;
    end;
  end;
end;

// ---------------------------------------------------------------------------
// Azioni post-installazione
// ---------------------------------------------------------------------------

procedure CurStepChanged(CurStep: TSetupStep);
var
  ProviderIdx : Integer;
  ApiKey      : String;
  EnvVarName  : String;
  ExePath     : String;
  PsArgs      : String;
  ResultCode  : Integer;
begin
  if CurStep <> ssPostInstall then Exit;

  // Determina provider selezionato
  ProviderIdx := 0;
  if ProviderPage.Values[1] then ProviderIdx := 1;
  if ProviderPage.Values[2] then ProviderIdx := 2;

  ExePath := ExpandConstant('{app}\{#AppExeName}');

  // --- 1. Salva API Key come variabile di sistema utente ---
  if ProviderIdx = 0 then EnvVarName := 'GOOGLE_API_KEY'
  else if ProviderIdx = 1 then EnvVarName := 'OPENAI_API_KEY'
  else EnvVarName := '';

  if EnvVarName <> '' then
  begin
    ApiKey := Trim(ApiKeyPage.Values[0]);
    if ApiKey <> '' then
    begin
      // HKCU\Environment e' lo storage delle variabili utente in Windows
      RegWriteStringValue(
        HKEY_CURRENT_USER, 'Environment',
        EnvVarName, ApiKey
      );
    end;
  end;

  // --- 2. Setup strumenti Visual Studio tramite PowerShell ---
  PsArgs :=
    '-NoProfile -ExecutionPolicy Bypass -File "' +
    ExpandConstant('{app}\{#PsScript}') + '" ' +
    '-Mode install ' +
    '-ExePath "' + ExePath + '" ' +
    '-ProviderIdx ' + IntToStr(ProviderIdx);

  if not Exec('powershell.exe', PsArgs, ExpandConstant('{app}'),
              SW_HIDE, ewWaitUntilTerminated, ResultCode) then
  begin
    MsgBox(
      'Impossibile eseguire lo script di configurazione Visual Studio.' + #13#10 +
      'Puoi configurare gli strumenti manualmente: vedi README_INSTALLER.md.',
      mbInformation, MB_OK
    );
  end
  else if ResultCode <> 0 then
  begin
    MsgBox(
      'La configurazione degli strumenti Visual Studio ha restituito un errore (codice ' +
      IntToStr(ResultCode) + ').' + #13#10 +
      'Verifica che Visual Studio sia chiuso e riprova, oppure configura manualmente.',
      mbInformation, MB_OK
    );
  end;
end;

// ---------------------------------------------------------------------------
// Uninstall: rimuove i tool VS e (opzionale) la env var
// ---------------------------------------------------------------------------

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  PsExe   : String;
  PsArgs  : String;
  ResCode : Integer;
  Answer  : Integer;
begin
  if CurUninstallStep <> usPostUninstall then Exit;

  // Rimuovi strumenti da Visual Studio usando lo script PS incluso nei file di sistema
  // (lo script viene copiato temporaneamente prima della disinstallazione)
  PsExe  := 'powershell.exe';
  PsArgs :=
    '-NoProfile -ExecutionPolicy Bypass -Command "' +
    '& { ' +
    '$key = ''HKCU:\Software\Microsoft\VisualStudio''; ' +
    'if (Test-Path $key) { ' +
    '  Get-ChildItem $key | Where-Object { $_.PSChildName -match ''\d+\.\d+_'' } | ForEach-Object { ' +
    '    $tk = "$($_.PSPath)\External Tools"; ' +
    '    if (Test-Path $tk) { ' +
    '      $n = [int](Get-ItemProperty $tk).ToolCount; ' +
    '      $rem = @(); ' +
    '      for ($i=0;$i -lt $n;$i++) { ' +
    '        $t=(Get-ItemProperty $tk -Name \"ToolTitle$i\" -EA SilentlyContinue).\"ToolTitle$i\"; ' +
    '        if ($t -notlike \"TestGen*\") { $rem += $i } ' +
    '      }; ' +
    '      $keep = $rem | ForEach-Object { ' +
    '        [PSCustomObject]@{T=(Get-ItemProperty $tk \"ToolTitle$_\").\"ToolTitle$_\";' +
    'C=(Get-ItemProperty $tk \"ToolCmd$_\").\"ToolCmd$_\";' +
    'A=(Get-ItemProperty $tk \"ToolArg$_\").\"ToolArg$_\";' +
    'D=(Get-ItemProperty $tk \"ToolDir$_\").\"ToolDir$_\";' +
    'O=(Get-ItemProperty $tk \"ToolOpt$_\").\"ToolOpt$_\"} ' +
    '      }; ' +
    '      for ($i=0;$i -lt $n;$i++){''ToolTitle'',''ToolCmd'',''ToolArg'',''ToolDir'',''ToolOpt'' | ForEach-Object { Remove-ItemProperty $tk -Name \"$_$i\" -EA SilentlyContinue }}; ' +
    '      for ($i=0;$i -lt $keep.Count;$i++){Set-ItemProperty $tk \"ToolTitle$i\" $keep[$i].T;Set-ItemProperty $tk \"ToolCmd$i\" $keep[$i].C;Set-ItemProperty $tk \"ToolArg$i\" $keep[$i].A;Set-ItemProperty $tk \"ToolDir$i\" $keep[$i].D;Set-ItemProperty $tk \"ToolOpt$i\" $keep[$i].O}; ' +
    '      Set-ItemProperty $tk ToolCount $keep.Count ' +
    '    } ' +
    '  } ' +
    '} ' +
    '}"';

  Exec(PsExe, PsArgs, '', SW_HIDE, ewWaitUntilTerminated, ResCode);

  // Chiedi se rimuovere anche la API key
  Answer := MsgBox(
    'Vuoi rimuovere anche la variabile di sistema con la API Key?' + #13#10 +
    '(GOOGLE_API_KEY / OPENAI_API_KEY)',
    mbConfirmation, MB_YESNO
  );
  if Answer = IDYES then
  begin
    RegDeleteValue(HKEY_CURRENT_USER, 'Environment', 'GOOGLE_API_KEY');
    RegDeleteValue(HKEY_CURRENT_USER, 'Environment', 'OPENAI_API_KEY');
  end;
end;
