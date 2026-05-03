"""Tests for spoken punctuation normalisation and auto-capitalisation."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest
from dictateanywhere.core.punctuation import (
    normalise_punctuation,
    auto_capitalise,
    process,
    clean_whisper_artifacts,
)


class TestNormalisePunctuation:
    def test_period(self):
        assert normalise_punctuation("hello period") == "hello ."

    def test_comma(self):
        assert normalise_punctuation("one comma two") == "one , two"

    def test_question_mark(self):
        assert normalise_punctuation("how are you question mark") == "how are you ?"

    def test_exclamation(self):
        assert normalise_punctuation("wow exclamation mark") == "wow !"

    def test_new_line(self):
        assert normalise_punctuation("line one new line line two") == "line one \n line two"

    def test_new_paragraph(self):
        result = normalise_punctuation("first paragraph new paragraph second")
        assert "\n\n" in result

    def test_open_close_quote(self):
        result = normalise_punctuation('open quote hello close quote')
        assert '"' in result

    def test_case_insensitive(self):
        assert normalise_punctuation("Hello PERIOD") == "Hello ."
        assert normalise_punctuation("Hello Period") == "Hello ."

    def test_no_change_when_no_keywords(self):
        text = "the quick brown fox"
        assert normalise_punctuation(text) == text

    def test_multiple_punctuation(self):
        result = normalise_punctuation("hello comma world period")
        assert "," in result
        assert "." in result

    def test_full_stop_alias(self):
        assert normalise_punctuation("end full stop") == "end ."

    def test_ellipsis(self):
        assert normalise_punctuation("and so on ellipsis") == "and so on …"

    def test_delete_that(self):
        result = normalise_punctuation("wrong word delete that")
        assert "delete that" not in result.lower()


class TestAutoCapitalise:
    def test_capitalise_at_start(self):
        assert auto_capitalise("hello world", "") == "Hello world"

    def test_capitalise_after_period(self):
        assert auto_capitalise("next sentence", "previous sentence.") == "Next sentence"

    def test_capitalise_after_question_mark(self):
        assert auto_capitalise("yes", "is this working?") == "Yes"

    def test_no_capitalise_mid_sentence(self):
        assert auto_capitalise("world", "hello ") == "world"

    def test_empty_text(self):
        assert auto_capitalise("", "anything") == ""

    def test_already_capitalised(self):
        assert auto_capitalise("Already", "") == "Already"

    def test_leading_whitespace_preserved(self):
        result = auto_capitalise("  hello", "")
        assert result == "  Hello"


class TestProcess:
    def test_full_pipeline(self):
        result = process("hello comma world period", "")
        assert "," in result
        assert "." in result
        # capitalised because previous_text is empty
        assert result[0].isupper()

    def test_skip_punctuation(self):
        result = process("hello comma world", apply_punctuation=False)
        assert "comma" in result
        assert "," not in result

    def test_skip_capitalise(self):
        result = process("hello", "", apply_capitalise=False)
        assert result[0].islower()


class TestCleanWhisperArtifacts:
    def test_removes_brackets(self):
        assert clean_whisper_artifacts("[Music] hello") == "hello"

    def test_removes_applause(self):
        assert clean_whisper_artifacts("[Applause]") == ""

    def test_removes_inaudible(self):
        assert clean_whisper_artifacts("(inaudible)") == ""

    def test_removes_lone_thank_you(self):
        assert clean_whisper_artifacts("Thank you.") == ""

    def test_keeps_real_text(self):
        assert clean_whisper_artifacts("Hello, how are you?") == "Hello, how are you?"

    def test_removes_lone_period(self):
        assert clean_whisper_artifacts(".") == ""
