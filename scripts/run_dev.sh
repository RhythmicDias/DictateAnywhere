#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# DictateAnywhere — Launch in development mode (macOS, foreground)
# ─────────────────────────────────────────────────────────────────────────────

VENV_DIR=".venv"
PYTHON="$VENV_DIR/bin/python"

if [ ! -f "$PYTHON" ]; then
    echo "ERROR: Python not found at $PYTHON."
    echo "Run  ./scripts/install.sh  first."
    exit 1
fi

# Set PYTHONPATH to the src directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PYTHONPATH="$SCRIPT_DIR/../src"

echo "[DictateAnywhere] Starting in development mode (foreground) ..."
"$PYTHON" -m dictateanywhere
