"""pytest configuration — ensures src/ is on sys.path for test discovery."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
