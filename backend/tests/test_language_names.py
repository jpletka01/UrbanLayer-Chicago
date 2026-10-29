"""Spanish chat answers are written in Mexican Spanish, and the name reaches both prompts that use it."""
from __future__ import annotations

from backend.prompts import LANGUAGE_INSTRUCTION
from backend.synthesizer import LANGUAGE_NAMES


def test_spanish_names_the_mexican_dialect_and_the_usted_register():
    assert "Mexican Spanish" in LANGUAGE_NAMES["es"]
    assert "usted" in LANGUAGE_NAMES["es"]


def test_the_name_is_in_the_synthesizer_instruction():
    instruction = LANGUAGE_INSTRUCTION.format(language_name=LANGUAGE_NAMES["es"])

    assert instruction.startswith("IMPORTANT: Respond entirely in Mexican Spanish")
    assert "Translate all prose, headers, and explanations into Mexican Spanish" in instruction
