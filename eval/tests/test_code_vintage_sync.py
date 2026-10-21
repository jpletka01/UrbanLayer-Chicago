"""The answer key states which code text it was built against. These fail after a
code refresh until the key (and the docs that quote it) are brought up to date, which
is the point: a refresh must not leave the benchmark claiming the old text silently."""

from __future__ import annotations

import json
from pathlib import Path

from eval import parcel_kit as k

ROOT = Path(__file__).resolve().parents[2]


def test_key_is_built_against_the_indexed_code_vintage():
    indexed = json.loads((ROOT / "backend" / "code_vintage.json").read_text())["current_through"]
    assert k.load_key()["code_current_through"] == indexed, (
        "the code was refreshed: re-check the answer key against the new text, then update "
        "code_current_through in eval/kit/parcels.json"
    )


def test_evals_md_quotes_the_keys_vintage():
    vintage = k.load_key()["code_current_through"]
    assert f"Code text is current through the Council Journal of {vintage}." in (ROOT / "EVALS.md").read_text()
