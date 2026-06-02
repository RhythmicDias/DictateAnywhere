@echo off
REM ─────────────────────────────────────────────────────────────────────────────
REM DictateAnywhere — Complete Uninstaller
REM
REM Removes:
REM   1. Running DictateAnywhere process (if active)
REM   2. Windows startup registry entry
REM   3. Azure API key from Windows Credential Manager
REM   4. App data folder  (%APPDATA%\DictateAnywhere)
REM      - config.json, logs, downloaded Whisper models
REM   5. Virtual environment (.venv folder)
REM   6. Optionally: the application folder itself
REM ─────────────────────────────────────────────────────────────────────────────

setlocal EnableDelayedExpansion
cd /d "%~dp0.."

echo.
echo  ============================================================
echo   DictateAnywhere Uninstaller
echo  ============================================================
echo.
echo  This will completely remove DictateAnywhere from your system.
echo  Press Ctrl+C NOW to cancel, or
pause

echo.
echo ── Step 1/5: Stopping DictateAnywhere if it is running ──────────────────────
taskkill /F /IM pythonw.exe /FI "WINDOWTITLE eq DictateAnywhere" >nul 2>&1
taskkill /F /IM python.exe  /FI "WINDOWTITLE eq DictateAnywhere" >nul 2>&1
REM Give it a moment to close
timeout /T 1 /NOBREAK >nul
echo   Done.

echo.
echo ── Step 2/5: Removing Windows startup registry entry ────────────────────────
reg delete "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v "DictateAnywhere" /f >nul 2>&1
if errorlevel 1 (
    echo   Not found (was not set to start with Windows — OK).
) else (
    echo   Removed startup entry.
)

echo.
echo ── Step 3/5: Removing Azure API key from Windows Credential Manager ─────────
set VENV_PYTHON=.venv\Scripts\python.exe
if exist "%VENV_PYTHON%" (
    "%VENV_PYTHON%" -c "import keyring; keyring.delete_password('DictateAnywhere', 'azure_speech_api_key')" >nul 2>&1
    if errorlevel 1 (
        echo   No Azure key found (already removed or never set — OK).
    ) else (
        echo   Azure API key removed from Windows Credential Manager.
    )
) else (
    echo   Virtual environment not found — skipping credential removal.
    echo   To remove manually: open Credential Manager → Windows Credentials
    echo   → find "DictateAnywhere" and delete it.
)

echo.
echo ── Step 4/5: Removing app data folder ───────────────────────────────────────
set APPDATA_DIR=%APPDATA%\DictateAnywhere
if exist "%APPDATA_DIR%" (
    echo   Removing: %APPDATA_DIR%
    rmdir /S /Q "%APPDATA_DIR%"
    if errorlevel 1 (
        echo   WARNING: Could not fully remove %APPDATA_DIR%
        echo   Close all File Explorer windows pointing there and try again.
    ) else (
        echo   Removed config, logs, and cached Whisper models.
    )
) else (
    echo   App data folder not found (already removed — OK).
)

echo.
echo ── Step 5/5: Removing virtual environment (.venv) ───────────────────────────
if exist ".venv" (
    echo   Removing .venv folder (this may take a moment) ...
    rmdir /S /Q ".venv"
    if errorlevel 1 (
        echo   WARNING: Could not fully remove .venv.
        echo   Close any terminals that have the venv activated and try again.
    ) else (
        echo   Virtual environment removed.
    )
) else (
    echo   .venv not found (already removed — OK).
)

echo.
echo  ============================================================
echo   Core uninstall complete.
echo  ============================================================
echo.
echo   The source code folder (this directory) was NOT deleted.
echo.
set /P REMOVE_DIR="  Delete the entire application folder too? [y/N]: "
if /I "!REMOVE_DIR!"=="y" (
    echo.
    echo   Scheduling folder deletion on next reboot via Windows scheduler ...
    REM We cannot delete the folder we are currently running from, so we
    REM use a scheduled self-delete via cmd /C after a brief delay.
    set "CURRENT_DIR=%~dp0.."
    start "" /B cmd /C "cd /d %SystemRoot% & timeout /T 2 /NOBREAK >nul & rmdir /S /Q ""%~dp0.."""
    echo   The application folder will be removed in a few seconds.
    echo   (If it is not removed automatically, delete it manually.)
) else (
    echo.
    echo   Application folder kept. You can delete it manually at any time.
)

echo.
echo  DictateAnywhere has been completely uninstalled. Goodbye!
echo.
pause
