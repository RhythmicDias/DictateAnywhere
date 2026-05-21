#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# DictateAnywhere — Complete Uninstaller (macOS)
#
# Removes:
#   1. Running DictateAnywhere processes
#   2. Keyring credentials from macOS Keychain
#   3. App data folder (~/Library/Application Support/DictateAnywhere)
#   4. Virtual environment (.venv folder)
#   5. Optionally: the application folder itself
# ─────────────────────────────────────────────────────────────────────────────

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(dirname "$SCRIPT_DIR")"

echo ""
echo "============================================================"
echo " DictateAnywhere Uninstaller"
echo "============================================================"
echo ""
echo "This will completely remove DictateAnywhere from your system."
read -p "Press Enter to continue, or Ctrl+C to cancel..."

echo ""
echo "── Step 1/4: Stopping DictateAnywhere processes ──────────────────"
# Kill any background python process running dictateanywhere
pkill -f -9 "dictateanywhere" >/dev/null 2>&1
sleep 1
echo "  Done."

echo ""
echo "── Step 2/4: Removing credentials from macOS Keychain ──────────"
PYTHON=".venv/bin/python"
if [ -f "$PYTHON" ]; then
    "$PYTHON" -c "
import keyring
for key in ['azure_speech_api_key', 'sarvam_api_key', 'gemini_api_key']:
    try:
        keyring.delete_password('DictateAnywhere', key)
        print(f'  Removed {key} from Keychain.')
    except Exception:
        pass
"
else
    echo "  Virtual environment not found — skipping Keychain cleanup."
fi

echo ""
echo "── Step 3/4: Removing App Data folder ──────────────────────────"
APPDATA_DIR="$HOME/Library/Application Support/DictateAnywhere"
if [ -d "$APPDATA_DIR" ]; then
    echo "  Removing: $APPDATA_DIR"
    rm -rf "$APPDATA_DIR"
    echo "  Removed config, logs, and cached Whisper models."
else
    echo "  App data folder not found (already removed — OK)."
fi

echo ""
echo "── Step 4/4: Removing virtual environment (.venv) ────────────────"
if [ -d ".venv" ]; then
    echo "  Removing .venv folder (this may take a moment)..."
    rm -rf ".venv"
    echo "  Virtual environment removed."
else
    echo "  .venv not found (already removed — OK)."
fi

echo ""
echo "============================================================"
echo " Core uninstall complete."
echo "============================================================"
echo ""
echo "The source code folder ($APP_DIR) was NOT deleted."
echo ""
read -p "Delete the entire application folder too? [y/N]: " REMOVE_DIR
if [[ "$REMOVE_DIR" =~ ^[Yy]$ ]]; then
    echo ""
    echo "Removing the application folder..."
    rm -rf "$APP_DIR"
    echo "Done. Goodbye!"
else
    echo ""
    echo "Application folder kept. You can delete it manually at any time."
fi
