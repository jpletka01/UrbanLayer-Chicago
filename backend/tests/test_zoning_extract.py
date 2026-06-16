"""Unit tests for zoning_extract helpers."""

import json

from backend.zoning_extract import _json_from_model_text


def test_strips_json_fence():
    # The historical bug: Haiku wraps JSON in ```json … ``` fences, so bare
    # json.loads fails at char 0 and extraction silently falls back to the table.
    raw = '```json\n{"far": 1.2, "max_height_ft": 45}\n```'
    assert json.loads(_json_from_model_text(raw)) == {"far": 1.2, "max_height_ft": 45}


def test_strips_bare_fence_without_language_tag():
    raw = '```\n{"far": 3.0}\n```'
    assert json.loads(_json_from_model_text(raw)) == {"far": 3.0}


def test_passes_through_bare_json():
    raw = '{"far": 0.9, "uses": ["residential"]}'
    assert json.loads(_json_from_model_text(raw)) == {"far": 0.9, "uses": ["residential"]}


def test_extracts_object_from_surrounding_prose():
    raw = 'Here are the standards:\n{"far": 2.0}\nLet me know if you need more.'
    assert json.loads(_json_from_model_text(raw)) == {"far": 2.0}


def test_handles_leading_trailing_whitespace():
    raw = '   \n  {"far": 1.0}  \n '
    assert json.loads(_json_from_model_text(raw)) == {"far": 1.0}
