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

echo [DictateAnywhere] Upgrading pip ...
%PIP% install --upgrade pip

echo.
echo [DictateAnywhere] Installing dependencies ...
%PIP% install -r requirements.txt

if errorlevel 1 (
    echo.
    echo ERROR: Dependency installation failed.
    echo Check the error above. Common fixes:
    echo   - Make sure Microsoft C++ Build Tools are installed
    echo   - Try: pip install --upgrade setuptools wheel
    pause
    exit /b 1
)

echo.
echo [DictateAnywhere] Installing DictateAnywhere in editable mode ...
%PIP% install -e .

echo.
echo ─────────────────────────────────────────────────────────────────────────────
echo  Installation complete!
echo.
echo  To run DictateAnywhere:
echo    %VENV_DIR%\Scripts\python.exe -m dictateanywhere
echo.
echo  Or use the shortcut:  scripts\run.bat
echo ─────────────────────────────────────────────────────────────────────────────
echo.
pause
