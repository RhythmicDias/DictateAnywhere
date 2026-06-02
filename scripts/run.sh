#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# DictateAnywhere — Launch the app (macOS, in the background)
# ─────────────────────────────────────────────────────────────────────────────

cd "$(dirname "$0")/.." || exit 1

VENV_DIR=".venv"
PYTHON="$VENV_DIR/bin/python"

if [ ! -f "$PYTHON" ]; then
    echo "ERROR: Python not found at $PYTHON."
    echo "Run  ./scripts/install.sh  first."
    exit 1
fi

# Set PYTHONPATH to the src directory
export PYTHONPATH="$(pwd)/src"

echo "Launching DictateAnywhere in the background..."
# Run in background with stdout/stderr redirected
nohup "$PYTHON" -m dictateanywhere >/dev/null 2>&1 &

echo "DictateAnywhere started in the background (PID: $!)."
