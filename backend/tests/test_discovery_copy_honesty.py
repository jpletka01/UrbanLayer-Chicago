"""What the page SAYS must match what the filters DO (source-confidence: no unsupported claims)."""

from __future__ import annotations

import json
import re
from pathlib import Path

from backend.discovery.compile_text import parse
from backend.discovery.registry import load as load_registry

ROOT = Path(__file__).resolve().parents[2]
EN_PAGES = ROOT / "frontend" / "src" / "locales" / "en" / "pages.json"
ES_PAGES = ROOT / "frontend" / "src" / "locales" / "es" / "pages.json"


def _discovery_strings(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))["discovery"]


def _assert_parses_completely(example: str) -> None:
    frag = parse(example)
    assert frag.filters, f"example {example!r} compiles to no filters"
    assert frag.meta.textResidual == [], f"example {example!r} drops words: {frag.meta.textResidual}"


def test_the_text_boxs_own_examples_parse_completely():
    """Every example the page offers for the text box must compile with nothing silently dropped.

    The compiler is English-only (rule-based, no model), so the Spanish strings must also offer
    an English phrase: a Spanish example would be an example that does nothing.
    """
    for path in (EN_PAGES, ES_PAGES):
        strings = _discovery_strings(path)
        placeholder = strings["searchPlaceholder"]
        quoted = re.search(r'"([^"]+)"', placeholder)
        assert quoted, placeholder
        _assert_parses_completely(quoted.group(1))
        _assert_parses_completely(strings["text"]["example"])
    assert _discovery_strings(EN_PAGES)["text"]["example"] == _discovery_strings(ES_PAGES)["text"]["example"]


def test_a_recipe_on_the_residential_group_does_not_claim_multifamily_zoning():
    """`zoning_group: residential` is every R district (RS, RT, RM): never say "MF" or "multifamily zoning"."""
    registry = load_registry()
    en = _discovery_strings(EN_PAGES)["topic"]
    for topic in registry.topics:
        preset = topic.presets.get("zoning_group")
        if not preset or "residential" not in preset.get("values", []):
            continue
        texts = [topic.label or "", topic.description or ""]
        texts += [en.get(topic.id, {}).get("label", ""), en.get(topic.id, {}).get("description", "")]
        for text in texts:
            assert not re.search(r"\bMF\b|multi-?family zoning|multifamily-zoned|\bRM/RT\b", text, re.I), (topic.id, text)
