@echo off
REM ─────────────────────────────────────────────────────────────────────────────
REM DictateAnywhere — Create virtual environment
REM Run this once before install.bat
REM ─────────────────────────────────────────────────────────────────────────────

setlocal

set VENV_DIR=.venv

echo [DictateAnywhere] Checking Python version ...
python --version 2>nul
if errorlevel 1 (
    echo ERROR: Python not found on PATH.
    echo Download Python 3.11, 3.12, or 3.13 (64-bit) from https://www.python.org/downloads/
    pause
    exit /b 1
)

echo.
echo [DictateAnywhere] Creating virtual environment in %VENV_DIR% ...
python -m venv %VENV_DIR%
if errorlevel 1 (
    echo ERROR: Failed to create virtual environment.
    echo Make sure Python 3.11 or newer is installed and on your PATH.
    pause
    exit /b 1
)

echo.
echo [DictateAnywhere] Virtual environment created successfully.
echo.
echo Next step: run  scripts\install.bat
echo.
pause
