@echo off
REM ─────────────────────────────────────────────────────────────────────────────
REM DictateAnywhere — Build standalone .exe with PyInstaller
REM Output: dist\DictateAnywhere\DictateAnywhere.exe
REM ─────────────────────────────────────────────────────────────────────────────

setlocal

set VENV_DIR=.venv
set PYTHON=%VENV_DIR%\Scripts\python.exe

if not exist "%PYTHON%" (
    echo ERROR: Virtual environment not found. Run scripts\install.bat first.
    pause
    exit /b 1
)

echo [DictateAnywhere] Installing PyInstaller ...
"%PYTHON%" -m pip install pyinstaller --quiet

echo.
echo [DictateAnywhere] Building executable ...
"%PYTHON%" -m PyInstaller ^
    --name "DictateAnywhere" ^
    --icon "assets/icon.ico" ^
    --windowed ^
    --onedir ^
    --add-data "assets;assets" ^
    --hidden-import "faster_whisper" ^
    --hidden-import "azure.cognitiveservices.speech" ^
    --hidden-import "keyring.backends.Windows" ^
    --hidden-import "sounddevice" ^
    --hidden-import "webrtcvad" ^
    --hidden-import "pystray._win32" ^
    --collect-all "faster_whisper" ^
    --collect-all "ctranslate2" ^
    --noconfirm ^
    src\dictateanywhere\main.py

if errorlevel 1 (
    echo.
    echo ERROR: Build failed. Check the output above.
    pause
    exit /b 1
)

echo.
echo =============================================================================
echo  Build complete!
echo  Executable: dist\DictateAnywhere\DictateAnywhere.exe
echo =============================================================================
echo.
pause
