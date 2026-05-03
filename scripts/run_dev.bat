@echo off
REM ─────────────────────────────────────────────────────────────────────────────
REM DictateAnywhere — Launch in development mode (console window visible)
REM ─────────────────────────────────────────────────────────────────────────────

setlocal

set VENV_DIR=.venv
set PYTHON=%VENV_DIR%\Scripts\python.exe

if not exist "%PYTHON%" (
    echo ERROR: python.exe not found at %PYTHON%.
    echo Run  scripts\install.bat  first.
    pause
    exit /b 1
)

REM Add src\ to PYTHONPATH so the app is found without needing "pip install -e ."
set PYTHONPATH=%~dp0..\src

echo [DictateAnywhere] Starting in development mode (console visible) ...
"%PYTHON%" -m dictateanywhere
pause
