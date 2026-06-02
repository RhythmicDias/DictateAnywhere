@echo off
REM ─────────────────────────────────────────────────────────────────────────────
REM DictateAnywhere — Create virtual environment
REM Run this once before install.bat
REM ─────────────────────────────────────────────────────────────────────────────

setlocal

cd /d "%~dp0.."

set VENV_DIR=.venv

echo [DictateAnywhere] Detecting Python version ...

set "PYTHON_CMD="

REM Try Python Launcher (py -3) first
py -3 -c "import sys; exit(0 if (3, 11) <= sys.version_info < (3, 14) else 1)" >nul 2>&1
if %errorlevel% equ 0 set "PYTHON_CMD=py -3"

if defined PYTHON_CMD goto python_detected

REM Try raw python command
python -c "import sys; exit(0 if (3, 11) <= sys.version_info < (3, 14) else 1)" >nul 2>&1
if %errorlevel% equ 0 set "PYTHON_CMD=python"

if defined PYTHON_CMD goto python_detected

echo ERROR: Python 3.11, 3.12, or 3.13 (64-bit) was not found on PATH.
echo Please install Python 3.11, 3.12, or 3.13 from https://www.python.org/downloads/
echo Make sure to check "Add python.exe to PATH" during installation.
pause
exit /b 1

:python_detected

echo [DictateAnywhere] Using Python:
%PYTHON_CMD% --version

echo.
echo [DictateAnywhere] Creating virtual environment in %VENV_DIR% ...
%PYTHON_CMD% -m venv %VENV_DIR%
if errorlevel 1 (
    echo ERROR: Failed to create virtual environment.
    pause
    exit /b 1
)

echo.
echo [DictateAnywhere] Virtual environment created successfully.
echo.
echo Next step: run  scripts\install.bat
echo.
pause
