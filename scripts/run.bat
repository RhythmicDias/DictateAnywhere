@echo off
REM ─────────────────────────────────────────────────────────────────────────────
REM DictateAnywhere — Launch the app
REM ─────────────────────────────────────────────────────────────────────────────

setlocal

set VENV_DIR=.venv
set PYTHON=%VENV_DIR%\Scripts\pythonw.exe

if not exist "%PYTHON%" (
    echo ERROR: pythonw.exe not found at %PYTHON%.
    echo Run  scripts\install.bat  first.
    pause
    exit /b 1
)

REM pythonw.exe suppresses the console window for a clean tray-app experience.
start "" "%PYTHON%" -m dictateanywhere
