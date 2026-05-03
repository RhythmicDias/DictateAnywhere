"""
Spoken punctuation normalisation and automatic capitalisation.

Converts spoken words like "period" → "." and ensures correct
capitalisation after sentence-ending punctuation.
"""

from __future__ import annotations

import re

# ── Spoken → symbol table ──────────────────────────────────────────────────────
# Order matters: longer phrases before shorter ones to avoid partial matches.
_PUNCT_MAP: list[tuple[str, str]] = [
    # Sentence endings
    ("full stop",          "."),
    ("period",             "."),
    ("exclamation mark",   "!"),
    ("exclamation point",  "!"),
    ("question mark",      "?"),

    # Pauses
    ("comma",              ","),
    ("semicolon",          ";"),
    ("colon",              ":"),

    # Structural
    ("new paragraph",      "\n\n"),
    ("new line",           "\n"),
    ("next line",          "\n"),
    ("line break",         "\n"),

    # Quotes
    ("open quote",         '"'),
    ("close quote",        '"'),
    ("open single quote",  "'"),
    ("close single quote", "'"),

    # Brackets / parens
    ("open parenthesis",   "("),
    ("close parenthesis",  ")"),
    ("open bracket",       "["),
    ("close bracket",      "]"),
    ("open brace",         "{"),
    ("close brace",        "}"),

    # Special characters
    ("dash",               "—"),
    ("hyphen",             "-"),
    ("ellipsis",           "…"),
    ("at sign",            "@"),
    ("hashtag",            "#"),
    ("percent",            "%"),
    ("ampersand",          "&"),
    ("asterisk",           "*"),
    ("slash",              "/"),
    ("backslash",          "\\"),
    ("equals sign",        "="),
    ("plus sign",          "+"),

    # Numbers / math
    ("times",              "×"),
    ("divided by",         "÷"),

    # Editing commands
    ("delete that",        ""),
    ("scratch that",       ""),
    ("undo that",          ""),
]

# Sentence-ending characters for auto-capitalisation
_SENTENCE_ENDS = frozenset(".!?\n")

# Build a compiled regex from the map (case-insensitive, word-boundary aware)
_pattern = re.compile(
    r"\b(" + "|".join(re.escape(spoken) for spoken, _ in _PUNCT_MAP) + r")\b",
    flags=re.IGNORECASE,
)
_lookup = {spoken.lower(): symbol for spoken, symbol in _PUNCT_MAP}


def normalise_punctuation(text: str) -> str:
    """
    Replace spoken punctuation words with their symbol equivalents.

    Example:
        "Hello comma how are you period" → "Hello, how are you."
    """

    def _replace(match: re.Match) -> str:
        return _lookup.get(match.group(0).lower(), match.group(0))

    return _pattern.sub(_replace, text)


def auto_capitalise(text: str, previous_text: str = "") -> str:
    """
    Capitalise the first letter of *text* if the preceding context ends a sentence
    or if it is the very beginning of a dictation session.
    """
    if not text:
        return text

    # Strip leading whitespace for the check but preserve it in output
    stripped = text.lstrip()
    if not stripped:
        return text

    # Capitalise if previous text ends with a sentence-ending character
    # (accounting for trailing spaces) or if there is no previous text.
    prev = previous_text.rstrip()
    should_cap = (not prev) or (prev[-1] in _SENTENCE_ENDS)

    if should_cap:
        leading = text[: len(text) - len(stripped)]
        return leading + stripped[0].upper() + stripped[1:]

    return text


def process(text: str, previous_text: str = "", apply_punctuation: bool = True,
            apply_capitalise: bool = True) -> str:
    """Full processing pipeline: punctuation → capitalisation."""
    if apply_punctuation:
        text = normalise_punctuation(text)
    if apply_capitalise:
        text = auto_capitalise(text, previous_text)
    return text


def clean_whisper_artifacts(text: str) -> str:
    """Remove common Whisper hallucination patterns."""
    patterns = [
        r"\[.*?\]",                    # [Music], [Applause]
        r"\(.*?\)",                    # (inaudible)
        r"^\s*thank you\s*\.?\s*$",   # lone "thank you" artefact
        r"^\s*you\s*$",               # lone "you" artefact
        r"^\s*\.\s*$",                # lone period
    ]
    for pat in patterns:
        text = re.sub(pat, "", text, flags=re.IGNORECASE)
    return text.strip()
