@echo off
REM ─────────────────────────────────────────────────────────────────────────────
REM DictateAnywhere — Create virtual environment
REM Run this once before install.bat
REM ─────────────────────────────────────────────────────────────────────────────

setlocal

set VENV_DIR=.venv

echo [DictateAnywhere] Creating virtual environment in %VENV_DIR% ...
python -m venv %VENV_DIR%
if errorlevel 1 (
    echo ERROR: Failed to create virtual environment.
    echo Make sure Python 3.11+ is installed and on your PATH.
    pause
    exit /b 1
)

echo.
echo [DictateAnywhere] Virtual environment created successfully.
echo.
echo Next step: run  scripts\install.bat
echo.
pause
