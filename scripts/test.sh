#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# DictateAnywhere — Run the test suite (macOS)
# ─────────────────────────────────────────────────────────────────────────────

cd "$(dirname "$0")/.." || exit 1

VENV_DIR=".venv"
PYTHON="$VENV_DIR/bin/python"

if [ ! -f "$PYTHON" ]; then
    echo "ERROR: Virtual environment not found. Run ./scripts/install.sh first."
    exit 1
fi

# Set PYTHONPATH to the src directory
export PYTHONPATH="$(pwd)/src"

echo "[DictateAnywhere] Installing pytest..."
"$PYTHON" -m pip install pytest --quiet

echo ""
echo "[DictateAnywhere] Running tests..."
"$PYTHON" -m pytest tests/ -v --tb=short
