@echo off
REM ─────────────────────────────────────────────────────────────────────────────
REM DictateAnywhere — Install all dependencies into the venv
REM Run scripts\create_venv.bat first if .venv does not exist.
REM ─────────────────────────────────────────────────────────────────────────────

setlocal

set VENV_DIR=.venv
set PYTHON=%VENV_DIR%\Scripts\python.exe

if not exist "%PYTHON%" (
    echo ERROR: Virtual environment not found at %VENV_DIR%.
    echo Run  scripts\create_venv.bat  first.
    pause
    exit /b 1
)

echo [DictateAnywhere] Step 1/3 — Upgrading pip, setuptools and wheel ...
REM Must use "python -m pip" (not pip.exe directly) to avoid file-lock on Windows
"%PYTHON%" -m pip install --upgrade pip setuptools wheel
if errorlevel 1 (
    echo WARNING: Could not fully upgrade pip/setuptools/wheel — continuing anyway.
)

echo.
echo [DictateAnywhere] Step 2/3 — Installing dependencies (prefer pre-built wheels) ...
"%PYTHON%" -m pip install --prefer-binary -r requirements.txt

if errorlevel 1 (
    echo.
    echo ERROR: Dependency installation failed.
    echo.
    echo Common fixes:
    echo   1. Make sure you are running Python 3.11 or 3.12 (64-bit^)
    echo      Check with: python --version
    echo   2. Try running this command manually and check the output:
    echo      %PYTHON% -m pip install --prefer-binary -r requirements.txt
    pause
    exit /b 1
)

echo.
echo [DictateAnywhere] Step 3/3 — Installing DictateAnywhere package ...
"%PYTHON%" -m pip install --no-build-isolation -e .

if errorlevel 1 (
    echo ERROR: Failed to install DictateAnywhere package.
    pause
    exit /b 1
)

echo.
echo =============================================================================
echo  Installation complete!
echo.
echo  To run DictateAnywhere:
echo    scripts\run.bat          (no console window -- tray app)
echo    scripts\run_dev.bat      (with console for debugging)
echo =============================================================================
echo.
pause
