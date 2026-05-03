@echo off
REM ─────────────────────────────────────────────────────────────────────────────
REM DictateAnywhere — Install all dependencies into the venv
REM Run scripts\create_venv.bat first if .venv does not exist.
REM ─────────────────────────────────────────────────────────────────────────────

setlocal

set VENV_DIR=.venv
set PIP=%VENV_DIR%\Scripts\pip.exe

if not exist "%VENV_DIR%\Scripts\python.exe" (
    echo ERROR: Virtual environment not found at %VENV_DIR%.
    echo Run  scripts\create_venv.bat  first.
    pause
    exit /b 1
)

echo [DictateAnywhere] Step 1/3 — Upgrading pip, setuptools and wheel ...
%PIP% install --upgrade pip setuptools wheel
if errorlevel 1 (
    echo ERROR: Could not upgrade pip/setuptools/wheel.
    pause
    exit /b 1
)

echo.
echo [DictateAnywhere] Step 2/3 — Installing dependencies (prefer pre-built wheels) ...
%PIP% install --prefer-binary -r requirements.txt

if errorlevel 1 (
    echo.
    echo ERROR: Dependency installation failed.
    echo.
    echo Common fixes:
    echo   1. Make sure you are running Python 3.11 or 3.12 (64-bit)
    echo      Check with: python --version
    echo   2. If azure-cognitiveservices-speech fails, try manually:
    echo      .venv\Scripts\pip install azure-cognitiveservices-speech --prefer-binary
    echo   3. If faster-whisper fails, try:
    echo      .venv\Scripts\pip install faster-whisper --prefer-binary
    pause
    exit /b 1
)

echo.
echo [DictateAnywhere] Step 3/3 — Installing DictateAnywhere package ...
%PIP% install --no-build-isolation -e .

echo.
echo =============================================================================
echo  Installation complete!
echo.
echo  To run DictateAnywhere:
echo    scripts\run.bat          (no console window — tray app)
echo    scripts\run_dev.bat      (with console for debugging)
echo =============================================================================
echo.
pause
