#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# DictateAnywhere — Create virtual environment on macOS
# Run this once before install.sh
# ─────────────────────────────────────────────────────────────────────────────

VENV_DIR=".venv"

echo "[DictateAnywhere] Checking Python version..."

# Try python3 first, then python
if command -v python3 >/dev/null 2>&1; then
    PYTHON_CMD="python3"
elif command -v python >/dev/null 2>&1; then
    PYTHON_CMD="python"
else
    echo "ERROR: Python not found on PATH."
    echo "Please install Python 3.11, 3.12, or 3.13 via Homebrew ('brew install python') or from https://www.python.org/downloads/"
    exit 1
fi

$PYTHON_CMD --version

echo ""
echo "[DictateAnywhere] Creating virtual environment in $VENV_DIR..."
$PYTHON_CMD -m venv "$VENV_DIR"
if [ $? -ne 0 ]; then
    echo "ERROR: Failed to create virtual environment."
    echo "Make sure Python 3.11 or newer is installed."
    exit 1
fi

echo ""
echo "[DictateAnywhere] Virtual environment created successfully."
echo ""
echo "Next step: run  ./scripts/install.sh"
echo ""
