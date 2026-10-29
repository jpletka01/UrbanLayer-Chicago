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


def test_the_text_boxs_own_example_parses_completely():
    """The placeholder example must turn into filters with nothing silently dropped."""
    for path in (EN_PAGES,):  # es example is checked by the Spanish pass (the compiler is English)
        placeholder = _discovery_strings(path)["searchPlaceholder"]
        example = re.search(r'"([^"]+)"', placeholder)
        assert example, placeholder
        frag = parse(example.group(1))
        assert frag.filters, f"example {example.group(1)!r} compiles to no filters"
        assert frag.meta.textResidual == [], f"example drops words: {frag.meta.textResidual}"


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
