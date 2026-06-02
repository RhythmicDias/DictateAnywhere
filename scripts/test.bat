@echo off
REM ─────────────────────────────────────────────────────────────────────────────
REM DictateAnywhere — Run the test suite
REM ─────────────────────────────────────────────────────────────────────────────

setlocal

cd /d "%~dp0.."

set VENV_DIR=.venv
set PYTHON=%VENV_DIR%\Scripts\python.exe

if not exist "%PYTHON%" (
    echo ERROR: Virtual environment not found. Run scripts\install.bat first.
    pause
    exit /b 1
)

REM Add src\ to PYTHONPATH
set PYTHONPATH=%~dp0..\src

echo [DictateAnywhere] Installing pytest ...
"%PYTHON%" -m pip install pytest --quiet

echo.
echo [DictateAnywhere] Running tests ...
"%PYTHON%" -m pytest tests\ -v --tb=short

pause
