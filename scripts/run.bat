@echo off
REM ─────────────────────────────────────────────────────────────────────────────
REM DictateAnywhere — Launch the app (no console window)
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

REM Add src\ to PYTHONPATH so the app is found without needing "pip install -e ."
set PYTHONPATH=%~dp0..\src

REM pythonw.exe suppresses the console window for a clean tray-app experience.
start "" "%PYTHON%" -m dictateanywhere
