"""Step 1 tests — the static filter registry artifact + loader/validation (03)."""

from __future__ import annotations

import copy

import pytest
from pydantic import ValidationError

from backend.discovery import registry as reg

# The 30 filters declared in 03-filter-registry.md, grouped by category.
EXPECTED_BY_CATEGORY = {
    "location": {"neighborhood", "ward", "radius", "transit_proximity"},
    "property_use": {"land_use", "vacancy", "lot_size", "building_size", "year_built", "units"},
    "zoning_dev": {"zoning_group", "density_band", "overlay", "adu_eligible", "aro_zone"},
    "incentives": {"tif", "opportunity_zone", "enterprise_zone", "sbif_nof"},
    "financial": {
        "assessed_value", "last_sale_price", "sale_recency", "price_per_sf", "improvement_ratio"
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
}


@pytest.fixture
def raw():
    """The shipped artifact as a plain dict (for defect-injection tests)."""
    import json
    return json.loads(reg._REGISTRY_PATH.read_text())


def test_shipped_registry_loads_and_validates():
    r = reg.load()
    assert r.version
    # 4 location + 6 property_use + 5 zoning_dev + 4 incentives + 5 financial + 5 condition_risk
    assert len(r.filters) == 29


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
