#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# DictateAnywhere — Run the test suite (macOS)
# ─────────────────────────────────────────────────────────────────────────────

VENV_DIR=".venv"
PYTHON="$VENV_DIR/bin/python"

if [ ! -f "$PYTHON" ]; then
    echo "ERROR: Virtual environment not found. Run ./scripts/install.sh first."
    exit 1
fi

# Set PYTHONPATH to the src directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PYTHONPATH="$SCRIPT_DIR/../src"

echo "[DictateAnywhere] Installing pytest..."
"$PYTHON" -m pip install pytest --quiet

echo ""
echo "[DictateAnywhere] Running tests..."
"$PYTHON" -m pytest tests/ -v --tb=short
