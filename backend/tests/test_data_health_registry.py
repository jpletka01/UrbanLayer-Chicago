"""The source registry: shape, ownership, and completeness against the code.

Completeness is the point (WS6 plan §3.3): a Socrata dataset id, an ArcGIS service URL, an
OVERLAY_LAYERS id or a committed data artifact in the code without a registry entry fails
here, so a new source can't ship without a freshness rule.
"""

import ast
import json
import re
import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import get_args

import pytest

from backend.data_health import registry as reg
from backend.data_health.registry import BY_ID, SOURCES, layer_id_of, socrata_locator
from backend.retrieval.regulatory.overlays import OVERLAY_LAYERS

ROOT = Path(__file__).resolve().parents[2]
_DATASET_ID = re.compile(r"^[a-z0-9]{4}-[a-z0-9]{4}$")
_SLUG = re.compile(r"^[a-z0-9_]+(\.[a-z0-9_]+)+$")


def _code_string_constants(paths: list[Path]) -> dict[str, set[str]]:
    """String literals in the given files, minus docstrings, keyed by relative path."""
    out: dict[str, set[str]] = {}
    for path in paths:
        tree = ast.parse(path.read_text())
        docstrings: set[int] = set()
        for node in ast.walk(tree):
            if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                body = node.body
                if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
                    docstrings.add(id(body[0].value))
        found = {
            n.value for n in ast.walk(tree)
            if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in docstrings
        }
        out[str(path.relative_to(ROOT))] = found
    return out


def _dataset_id_candidates(paths: list[Path]) -> dict[str, set[str]]:
    """Strings that are Socrata dataset ids. An id with a digit is recognised anywhere; one made only
    of letters (``csik-bsws``) looks like a hyphenated word, so it counts only where it is named as a
    dataset: assigned to a ``*dataset*`` name or passed as the first argument to a Socrata helper."""
    out: dict[str, set[str]] = {}
    for path in paths:
        tree = ast.parse(path.read_text())
        found = {c for c in _code_string_constants([path])[str(path.relative_to(ROOT))]
                 if _DATASET_ID.match(c) and re.search(r"\d", c) and re.search(r"[a-z]", c)}
        for node in ast.walk(tree):
            if isinstance(node, (ast.Assign, ast.AnnAssign)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                names = [t.id if isinstance(t, ast.Name) else getattr(t, "attr", "") for t in targets]
                if any("dataset" in n.lower() for n in names) and isinstance(node.value, ast.Constant) \
                        and isinstance(node.value.value, str) and _DATASET_ID.match(node.value.value):
                    found.add(node.value.value)
            elif isinstance(node, ast.Call) and node.args and isinstance(node.args[0], ast.Constant):
                fn = node.func.id if isinstance(node.func, ast.Name) else getattr(node.func, "attr", "")
                if fn in {"socrata_get", "grouped_count", "socrata_aggregate"} and isinstance(node.args[0].value, str) \
                        and _DATASET_ID.match(node.args[0].value):
                    found.add(node.args[0].value)
        out[str(path.relative_to(ROOT))] = found
    return out


def _source_files() -> list[Path]:
    b = ROOT / "backend"
    files = [b / "config.py", b / "main.py"]
    for sub in ("retrieval", "discovery"):
        files += [p for p in (b / sub).rglob("*.py")]
    return sorted(files)


def test_ids_are_unique_slugs():
    ids = [s.id for s in SOURCES]
    assert len(ids) == len(set(ids))
    assert all(_SLUG.match(i) for i in ids), [i for i in ids if not _SLUG.match(i)]
    assert 70 <= len(SOURCES) <= 95  # the plan's inventory is about 75


def test_enumerated_fields_are_valid():
    tiers, kinds, severities = (get_args(getattr(reg, n)) for n in ("Tier", "Kind", "Severity"))
    surfaces = get_args(reg.Surface)
    for s in SOURCES:
        assert s.tier in tiers and s.kind in kinds and s.severity in severities, s.id
        assert set(s.surfaces) <= set(surfaces), s.id
        assert s.name and s.publisher and s.locator, s.id


def test_every_owner_module_exists():
    for s in SOURCES:
        assert s.owner_modules, s.id
        for m in s.owner_modules:
            assert (ROOT / m).exists(), f"{s.id}: owner module {m} does not exist"


def test_every_source_has_a_freshness_rule():
    """A date tolerance, a frozen label, an availability/coherence check, a structural contract,
    or an explicit placeholder for a probe that a later milestone adds."""
    for s in SOURCES:
        has_rule = (
            s.warn_days is not None or s.alarm_days is not None or s.frozen is not None
            or s.availability_only or s.contract is not None or s.probe == "none"
        )
        assert has_rule, f"{s.id} has no freshness rule"


def test_tolerances_are_ordered():
    for s in SOURCES:
        if s.warn_days is not None and s.alarm_days is not None:
            assert s.warn_days < s.alarm_days, s.id


def test_acks_are_reviewable():
    acks = [s for s in SOURCES if s.ack]
    assert acks, "day one starts with known-stale sources acked"
    for s in acks:
        assert isinstance(s.ack.until, date) and s.ack.until > date(2026, 10, 21), s.id
        assert len(s.ack.reason) > 40 and s.ack.owner, s.id


def test_frozen_sources_state_what_they_are_frozen_at():
    for s in SOURCES:
        if s.frozen:
            assert s.frozen.as_of and s.frozen.label, s.id
            assert s.warn_days is None and s.alarm_days is None, f"{s.id}: frozen sources alarm on change, not age"


def test_critical_set_matches_the_plan():
    critical = {s.id for s in SOURCES if s.severity == "critical"}
    for sid in ("chi.zoning.districts", "cook.parcel_universe", "cook.address_points", "cook.assessor.values",
                "cook.ptaxsim", "code.municipal_text", "code.qdrant_index", "artifact.zoning_cache",
                "code.hand_table.zoning_definitions", "chi.clerk.legislation", "census.geocoder"):
        assert sid in critical, sid
    assert {s.id for s in SOURCES if s.id.startswith("chi.zoning.overlay.")} <= critical


def test_known_stale_sources_are_in_the_plans_day_one_table():
    for sid in ("cook.address_points", "chi.vacant_buildings", "chi.nof_large"):
        assert BY_ID[sid].ack, sid
    assert BY_ID["chi.socioeconomic_2008_2012"].retired


# --- completeness against the code ------------------------------------------------------------

def test_every_socrata_dataset_id_in_the_code_is_registered():
    registered = {socrata_locator(s)[1] for s in SOURCES if s.kind == "socrata"}
    missing: dict[str, list[str]] = {}
    for path, ids in _dataset_id_candidates(_source_files()).items():
        for c in ids - registered:
            missing.setdefault(c, []).append(path)
    assert not missing, f"Socrata dataset ids with no registry entry: {missing}"


def test_every_arcgis_service_url_in_the_code_is_registered():
    locators = [s.locator for s in SOURCES if s.kind == "arcgis_layer"]
    missing: dict[str, str] = {}
    for path, consts in _code_string_constants(_source_files()).items():
        for c in consts:
            if "/rest/services" in c and c.startswith("http") and ("MapServer" in c or "FeatureServer" in c):
                if not any(c.startswith(loc) or loc.startswith(c.rstrip("/")) for loc in locators):
                    missing[c] = path
    assert not missing, f"ArcGIS service URLs with no registry entry: {missing}"


def test_registry_covers_exactly_the_overlay_layers():
    in_registry = {layer_id_of(s) for s in SOURCES if s.id.startswith("chi.zoning.overlay.")}
    assert in_registry == set(OVERLAY_LAYERS)
    for lid, meta in OVERLAY_LAYERS.items():
        assert BY_ID[f"chi.zoning.overlay.{meta['type']}"].locator.endswith(f"/MapServer/{lid}")


def test_layer_7_stays_out():
    """Layer 7 is the CHRS survey, not designations (F8, 2026-10-02): never queried, never registered."""
    assert 7 not in OVERLAY_LAYERS
    assert 7 not in {layer_id_of(s) for s in SOURCES}


def test_every_committed_data_artifact_is_registered():
    try:
        out = subprocess.run(
            ["git", "ls-files", "ingestion/data"], cwd=ROOT, capture_output=True, text=True, check=True, timeout=20,
        ).stdout.split()
    except (OSError, subprocess.SubprocessError):
        pytest.skip("not a git checkout")
    artifacts = {p for p in out if not p.startswith("ingestion/data/sections/")}
    if not artifacts:
        pytest.skip("no tracked artifacts (not a git checkout)")
    registered = {s.locator for s in SOURCES if s.kind == "artifact"}
    assert artifacts <= registered, f"committed artifacts with no registry entry: {sorted(artifacts - registered)}"


def test_hand_table_is_verified_against_the_served_code_vintage():
    """After each code refresh, someone re-verifies the hand table (test_zoning_ordinance_parity)
    and moves VERIFIED_AGAINST. This fails the refresh PR until they do."""
    from backend.retrieval import zoning_definitions

    vintage = json.loads((ROOT / "backend" / "code_vintage.json").read_text())["current_through"]
    assert zoning_definitions.VERIFIED_AGAINST == vintage


# --- import weight ---------------------------------------------------------------------------

def test_importing_the_checker_loads_none_of_the_serving_stack():
    code = (
        "import sys, backend.data_health.check\n"
        "heavy = [m for m in sys.modules if m.split('.')[0] in {'torch', 'sentence_transformers', 'transformers', 'numpy', "
        "'qdrant_client', 'weasyprint', 'matplotlib'} or m == 'backend.main' or m.startswith('backend.discovery')]\n"
        "print(sorted(heavy))\n"
    )
    out = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr
    assert out.stdout.strip() == "[]", out.stdout
