"""
Word corrections — user-defined text replacements applied after transcription.

Stored in  %APPDATA%\\DictateAnywhere\\corrections.json  as a JSON array:
    [{"from": "acme", "to": "Acme Corp"}, ...]

Matching is case-insensitive whole-word (\\b word-boundary regex).
Replacement is verbatim — exactly the "to" string, no case adjustment.
Longer "from" patterns are applied first so more-specific rules win.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import List, Tuple

logger = logging.getLogger(__name__)


class CorrectionsManager:
    """Load, save, and apply user-defined word corrections."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._corrections: List[Tuple[str, str]] = []
        self._patterns: list[tuple[re.Pattern, str]] = []
        self.load()

    # ── Public API ─────────────────────────────────────────────────────────────

    @property
    def corrections(self) -> List[Tuple[str, str]]:
        """Return a copy of all (from, to) pairs."""
        return list(self._corrections)

    def set_corrections(self, corrections: List[Tuple[str, str]]) -> None:
        """Replace the full corrections list and recompile patterns."""
        cleaned = [(f.strip(), t.strip()) for f, t in corrections if f.strip()]
        # Longest "from" first so "going to" wins over "going"
        self._corrections = sorted(cleaned, key=lambda x: len(x[0]), reverse=True)
        self._compile()

    def apply(self, text: str) -> str:
        """Apply all corrections to *text* and return the result."""
        for pattern, replacement in self._patterns:
            text = pattern.sub(replacement, text)
        return text

    def load(self) -> None:
        if not self._path.exists():
            return
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            pairs = [(item["from"], item["to"]) for item in data if item.get("from")]
            self._corrections = sorted(pairs, key=lambda x: len(x[0]), reverse=True)
            self._compile()
            logger.info("Loaded %d word corrections from %s", len(self._corrections), self._path)
        except Exception as exc:
            logger.warning("Failed to load corrections: %s", exc)
            self._corrections = []
            self._patterns = []

    def save(self) -> None:
        try:
            # Save in entry order (unsorted) for display consistency
            data = [{"from": f, "to": t} for f, t in self._corrections]
            tmp = self._path.with_suffix(".tmp")
            tmp.write_text(
                json.dumps(data, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            tmp.replace(self._path)
            logger.info("Saved %d word corrections", len(self._corrections))
        except Exception as exc:
            logger.error("Failed to save corrections: %s", exc)

    # ── Internal ───────────────────────────────────────────────────────────────

    def _compile(self) -> None:
        """Pre-compile regex patterns for fast application."""
        self._patterns = []
        for from_word, to_word in self._corrections:
            try:
                pat = re.compile(
                    r"\b" + re.escape(from_word) + r"\b",
                    re.IGNORECASE,
                )
                self._patterns.append((pat, to_word))
            except re.error as exc:
                logger.warning("Invalid correction pattern %r: %s", from_word, exc)
