#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# DictateAnywhere — Install all dependencies into the venv (macOS)
# Run scripts/create_venv.sh first if .venv does not exist.
# ─────────────────────────────────────────────────────────────────────────────

cd "$(dirname "$0")/.." || exit 1

VENV_DIR=".venv"
PYTHON="$VENV_DIR/bin/python"

if [ ! -f "$PYTHON" ]; then
    echo "ERROR: Virtual environment not found at $VENV_DIR."
    echo "Run  ./scripts/create_venv.sh  first."
    exit 1
fi

# Try to check if Homebrew's portaudio is installed (useful for sounddevice/pyaudio)
if command -v brew >/dev/null 2>&1; then
    if ! brew list portaudio >/dev/null 2>&1; then
        echo "[DictateAnywhere] Tip: portaudio is not installed. Installing portaudio via Homebrew..."
        brew install portaudio
    else
        echo "[DictateAnywhere] Portaudio found via Homebrew."
    fi
else
    echo "[DictateAnywhere] Warning: Homebrew not found. If audio recording fails to install, please install Homebrew and run: brew install portaudio"
fi

echo "[DictateAnywhere] Step 1/2 — Upgrading pip, setuptools and wheel..."
"$PYTHON" -m pip install --upgrade pip setuptools wheel
if [ $? -ne 0 ]; then
    echo "WARNING: Could not fully upgrade pip/setuptools/wheel — continuing anyway."
fi

echo ""
echo "[DictateAnywhere] Step 2/2 — Installing dependencies in editable mode..."
# We use -e . to install according to pyproject.toml platform markers
"$PYTHON" -m pip install --prefer-binary -e .
if [ $? -ne 0 ]; then
    echo ""
    echo "ERROR: Dependency installation failed."
    echo ""
    echo "Common fixes on macOS:"
    echo "  1. Ensure you have the Xcode Command Line Tools installed:"
    echo "     xcode-select --install"
    echo "  2. Ensure you have Homebrew and portaudio installed:"
    echo "     brew install portaudio"
    exit 1
fi

echo ""
echo "[DictateAnywhere] Step 3/3 — Downloading font assets..."
"$PYTHON" scripts/download_fonts.py
if [ $? -ne 0 ]; then
    echo "WARNING: Font download failed — system fallbacks will be used."
fi

echo ""
echo "============================================================================="
echo " Installation complete!"
echo ""
echo " To run DictateAnywhere:"
echo "   ./scripts/run.sh          (no console window -- tray app/floating widget)"
echo "   ./scripts/run_dev.sh      (with console for debugging)"
echo "============================================================================="
echo ""
