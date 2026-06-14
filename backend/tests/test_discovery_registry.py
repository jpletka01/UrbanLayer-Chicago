"""Step 1 tests — the static filter registry artifact + loader/validation (03)."""

from __future__ import annotations

import copy

import pytest
from pydantic import ValidationError

from backend.discovery import registry as reg

# The 32 filters (29 original + PR2's value_percentile/upside_score/is_teardown_candidate),
# grouped by category.
EXPECTED_BY_CATEGORY = {
    "location": {"neighborhood", "ward", "radius", "transit_proximity"},
    "property_use": {"land_use", "vacancy", "lot_size", "building_size", "year_built", "units"},
    "zoning_dev": {
        "zoning_group", "density_band", "overlay", "adu_eligible", "aro_zone",
        "upside_score", "is_teardown_candidate"
    },
    "incentives": {"tif", "opportunity_zone", "enterprise_zone", "sbif_nof"},
    "financial": {
        "assessed_value", "last_sale_price", "sale_recency", "price_per_sf",
        "improvement_ratio", "value_percentile"
    },
    "condition_risk": {
        "open_violations", "f311_redflags", "floodplain", "brownfield", "crime_index"
    },
}

EXPECTED_KINDS = {
    "neighborhood": "region", "ward": "region", "radius": "region",
    "transit_proximity": "range", "land_use": "enum", "vacancy": "flag",
    "lot_size": "range", "building_size": "range", "year_built": "range", "units": "range",
    "zoning_group": "enum", "density_band": "range", "overlay": "enum",
    "adu_eligible": "flag", "aro_zone": "flag", "tif": "flag", "opportunity_zone": "flag",
    "enterprise_zone": "flag", "sbif_nof": "flag", "assessed_value": "range",
    "last_sale_price": "range", "sale_recency": "range", "price_per_sf": "range",
    "improvement_ratio": "range", "open_violations": "range", "f311_redflags": "range",
    "floodplain": "flag", "brownfield": "flag", "crime_index": "range",
    "upside_score": "range", "is_teardown_candidate": "flag", "value_percentile": "range",
}


@pytest.fixture
def raw():
    """The shipped artifact as a plain dict (for defect-injection tests)."""
    import json
    return json.loads(reg._REGISTRY_PATH.read_text())


def test_shipped_registry_loads_and_validates():
    r = reg.load()
    assert r.version
    # 4 location + 6 property_use + 7 zoning_dev + 4 incentives + 6 financial + 5 condition_risk
    assert len(r.filters) == 32


def test_all_expected_filters_present_with_correct_category_and_kind():
    r = reg.load()
    by_cat: dict[str, set[str]] = {}
    for f in r.filters:
        by_cat.setdefault(f.category, set()).add(f.id)
    assert by_cat == EXPECTED_BY_CATEGORY
    assert {f.id: f.kind for f in r.filters} == EXPECTED_KINDS


def test_every_filter_has_unknown_policy():
    r = reg.load()
    for f in r.filters:
        assert f.unknownPolicy in ("exclude", "include")


def test_enum_filters_have_values_others_do_not():
    r = reg.load()
    for f in r.filters:
        if f.kind == "enum":
            assert f.enumValues, f.id
        else:
            assert f.enumValues is None, f.id


def test_default_sort_key_is_sortable():
    r = reg.load()
    assert r.defaultSort.key in r.sortable_keys()


def test_all_contradicts_ids_resolve():
    r = reg.load()
    ids = {f.id for f in r.filters}
    for f in r.filters:
        for c in f.contradicts:
            assert c in ids, f"{f.id} contradicts unknown {c}"


def test_accessors():
    r = reg.load()
    assert r.filter_def("lot_size").field == "land_sqft"
    assert r.filter_def("tif").kind == "flag"
    assert "pin" in r.sortable_keys()
    # The assessed_value SORT key points at the sort-only field (null for exempt/$0);
    # the assessed_value FILTER stays on the real value (PR3 0/exempt reconciliation).
    assert r.sort_field("assessed_value") == "total_assessed_value_sortkey"
    assert r.filter_def("assessed_value").field == "total_assessed_value"
    with pytest.raises(KeyError):
        r.filter_def("nope")
    with pytest.raises(KeyError):
        r.sort_field("nope")


# --- defect injection: every guard raises -----------------------------------


def test_duplicate_filter_id_raises(raw):
    raw["filters"].append(copy.deepcopy(raw["filters"][0]))
    with pytest.raises(ValidationError):
        reg.Registry.model_validate(raw)


def test_missing_unknown_policy_raises(raw):
    del raw["filters"][0]["unknownPolicy"]
    with pytest.raises(ValidationError):
        reg.Registry.model_validate(raw)


def test_bad_kind_raises(raw):
    raw["filters"][0]["kind"] = "bogus"
    with pytest.raises(ValidationError):
        reg.Registry.model_validate(raw)


def test_enum_without_values_raises(raw):
    land_use = next(f for f in raw["filters"] if f["id"] == "land_use")
    land_use["enumValues"] = []
    with pytest.raises(ValidationError):
        reg.Registry.model_validate(raw)


def test_enum_values_on_non_enum_raises(raw):
    vacancy = next(f for f in raw["filters"] if f["id"] == "vacancy")
    vacancy["enumValues"] = ["x"]
    with pytest.raises(ValidationError):
        reg.Registry.model_validate(raw)


def test_dangling_contradicts_raises(raw):
    raw["filters"][0]["contradicts"] = ["does_not_exist"]
    with pytest.raises(ValidationError):
        reg.Registry.model_validate(raw)


def test_default_sort_not_in_sort_keys_raises(raw):
    raw["defaultSort"] = {"key": "not_a_sort_key", "dir": "asc"}
    with pytest.raises(ValidationError):
        reg.Registry.model_validate(raw)


# --- PR2: range metadata + requires + hand-authored labels ------------------


def test_default_sort_is_assessed_value_asc():
    # PR2 flips the default off the meaningless pin order to cheapest-first.
    assert reg.load().defaultSort == reg.SortSpec(key="assessed_value", dir="asc")


def test_every_filter_has_a_hand_authored_label():
    # Labels kill humanize() for display — every filter must carry one.
    for f in reg.load().filters:
        assert f.label, f.id


def test_range_filters_carry_range_metadata():
    r = reg.load()
    for f in r.filters:
        if f.kind == "range":
            assert f.range is not None, f.id
            assert f.range.domain[0] <= f.range.domain[1], f.id


def test_single_bound_controls_are_declared():
    r = reg.load()
    assert r.filter_def("transit_proximity").range.boundMode == "max"
    assert r.filter_def("sale_recency").range.boundMode == "max"
    assert r.filter_def("value_percentile").range.boundMode == "max"
    assert r.filter_def("upside_score").range.boundMode == "min"


def test_density_band_declares_its_dependency():
    assert reg.load().filter_def("density_band").requires == ["zoning_group"]


def test_enum_labels_cover_their_values():
    r = reg.load()
    land_use = r.filter_def("land_use")
    assert set(land_use.enumLabels) == set(land_use.enumValues)
    assert land_use.enumLabels["multi_family"] == "Multifamily"


def test_topics_present_and_reference_known_filters_and_sortkeys():
    r = reg.load()
    assert len(r.topics) == 6
    ids = {f.id for f in r.filters}
    keys = r.sortable_keys()
    for t in r.topics:
        assert t.label and t.description, t.id
        for fid in t.presets:
            assert fid in ids, f"{t.id} -> {fid}"
        if t.defaultSort:
            assert t.defaultSort.key in keys, t.id


def test_new_derived_filters_present():
    r = reg.load()
    for fid in ("value_percentile", "upside_score", "is_teardown_candidate"):
        assert r.filter_def(fid)  # raises KeyError if missing
    assert r.sort_field("value_percentile") == "value_percentile"
    assert r.sort_field("upside_score") == "upside_score"


def test_range_metadata_on_non_range_raises(raw):
    vacancy = next(f for f in raw["filters"] if f["id"] == "vacancy")
    vacancy["range"] = {"domain": [0, 1], "step": 1, "boundMode": "both", "display": "number"}
    with pytest.raises(ValidationError):
        reg.Registry.model_validate(raw)


def test_enum_labels_for_unknown_value_raises(raw):
    land_use = next(f for f in raw["filters"] if f["id"] == "land_use")
    land_use["enumLabels"]["not_a_value"] = "Nope"
    with pytest.raises(ValidationError):
        reg.Registry.model_validate(raw)


def test_dangling_requires_raises(raw):
    raw["filters"][0]["requires"] = ["does_not_exist"]
    with pytest.raises(ValidationError):
        reg.Registry.model_validate(raw)
