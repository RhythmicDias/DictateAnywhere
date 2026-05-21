#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# DictateAnywhere — Launch the app (macOS, in the background)
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

echo "Launching DictateAnywhere in the background..."
# Run in background with stdout/stderr redirected
nohup "$PYTHON" -m dictateanywhere >/dev/null 2>&1 &

echo "DictateAnywhere started in the background (PID: $!)."
