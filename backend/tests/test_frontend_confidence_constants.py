"""The frontend prints "needs N" in a withheld sentence from display copies of the thresholds
(frontend/src/lib/confidence.ts DISPLAY_THRESHOLDS). The state itself always comes from the
backend entry; these copies only fill in the minimum, so they must not drift from provenance.py."""
import re
from pathlib import Path

from backend import provenance as p

SRC = (Path(__file__).resolve().parents[2] / "frontend/src/lib/confidence.ts").read_text()


def _ts_constant(name: str) -> float:
    m = re.search(rf"\b{name}:\s*([0-9.]+)", SRC)
    assert m, f"{name} not found in confidence.ts DISPLAY_THRESHOLDS"
    return float(m.group(1))


def test_display_thresholds_match_the_backend():
    assert _ts_constant("hideCoverageBelow") == p.HIDE_COVERAGE_BELOW
    assert _ts_constant("hideNBelow") == p.HIDE_N_BELOW
    assert _ts_constant("compsHideNBelow") == p.COMPS_HIDE_N_BELOW
    assert _ts_constant("hideCvAbove") == p.HIDE_CV_ABOVE


def test_every_confidence_reason_has_a_frontend_sentence():
    """A withheld reason the frontend doesn't know would print the generic line; keep them in step."""
    for reason in ("small_sample", "low_coverage", "high_cv"):
        assert f'"{reason}"' in SRC


def test_frontend_method_keys_cover_every_backend_method():
    import json

    en = json.loads((Path(__file__).resolve().parents[2] / "frontend/src/locales/en/common.json").read_text())
    missing = set(p.METHOD_TEXT) - set(en["confidence"]["method"])
    assert not missing, f"no caption text for method(s): {sorted(missing)}"
    tiers = set(en["confidence"]["tier"])
    assert set(p.TIER_ORDER) <= tiers
