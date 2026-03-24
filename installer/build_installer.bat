@echo off
setlocal

echo.
echo ============================================================
echo  TestGenerator - Build Installer
echo ============================================================
echo.

:: ---------------------------------------------------------------------------
:: Percorso Inno Setup (cambia se e' installato altrove)
:: ---------------------------------------------------------------------------
set ISCC="C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if not exist %ISCC% (
    set ISCC="C:\Program Files\Inno Setup 6\ISCC.exe"
)
if not exist %ISCC% (
    echo [ERRORE] Inno Setup 6 non trovato.
    echo Scaricalo da: https://jrsoftware.org/isinfo.php
    echo Oppure aggiorna il percorso ISCC in questo file .bat
    pause
    exit /b 1
)

:: ---------------------------------------------------------------------------
:: Step 1 - Build .exe con PyInstaller
:: ---------------------------------------------------------------------------
echo [1/2] Build TestGenerator.exe con PyInstaller...
echo.

cd /d "%~dp0..\test_generator"

pyinstaller --onefile --paths . --collect-all tree_sitter_c_sharp --name TestGenerator main.py
if %ERRORLEVEL% neq 0 (
    echo.
    echo [ERRORE] PyInstaller ha fallito. Verifica che:
    echo   - Python sia installato e nel PATH
    echo   - PyInstaller sia installato: pip install pyinstaller
    echo   - Le dipendenze siano installate: pip install -r requirements.txt
    pause
    exit /b 1
)

echo.
echo [OK] TestGenerator.exe creato in test_generator\dist\

:: ---------------------------------------------------------------------------
:: Step 2 - Compila installer con Inno Setup
:: ---------------------------------------------------------------------------
echo.
echo [2/2] Compilazione installer con Inno Setup...
echo.

cd /d "%~dp0"

%ISCC% installer.iss
if %ERRORLEVEL% neq 0 (
    echo.
    echo [ERRORE] Inno Setup ha fallito.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo  Build completata!
echo  Installer: installer\dist_installer\TestGeneratorSetup_1.0.exe
echo ============================================================
echo.
pause
