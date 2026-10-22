"""WS6 M4: contracts (fields we read, value sets, count bands) on top of the freshness rules."""

import asyncio
import json
from dataclasses import replace
from datetime import date
from pathlib import Path

import httpx
import pytest

from backend.data_health import contracts, probes
from backend.data_health.evaluate import ProbeError, ProbeResult, evaluate
from backend.data_health.registry import BY_ID, FIELDS_READ_PATH, SOURCES, Contract, load_fields_read

FX = Path(__file__).parent / "fixtures" / "data_health"
TODAY = date(2026, 10, 21)


def fx(name):
    return json.loads((FX / name).read_text())


# --- value sets --------------------------------------------------------------------------------------

def test_zone_classes_must_start_with_a_known_family():
    spec = BY_ID["chi.zoning.districts"]
    ok = ProbeResult(published=TODAY, values={"ZONE_CLASS": ("B3-2", "RM4-.5", "PD 835", "PMD 10", "POS-1", "T", "DX-16")})
    assert evaluate(spec, ok, TODAY).state != "alarm"
    bad = ProbeResult(published=TODAY, values={"ZONE_CLASS": ("B3-2", "XZ-9", "ZZ")})
    s = evaluate(spec, bad, TODAY)
    assert s.state == "alarm" and "ZONE_CLASS" in s.reason and "'XZ-9'" in s.reason and "'ZZ'" in s.reason


def test_the_zone_families_cover_every_class_the_zoning_table_knows():
    """A district family in our table that the contract rejects would alarm on a healthy layer."""
    from backend.data_health.registry import ZONE_FAMILIES
    from backend.retrieval.zoning_definitions import ZONE_CLASS_DATA

    assert ZONE_CLASS_DATA
    for zone in ZONE_CLASS_DATA:
        assert zone.upper().startswith(ZONE_FAMILIES), zone


@pytest.mark.parametrize("source,field,good,bad", [
    ("chi.zoning.overlay.historic_district", "LANDMARK", ("Y", "N"), ("Y", "Maybe")),
    ("cook.address_points", "st_predir", ("NORTH", "WEST"), ("NORTH", "UP")),
])
def test_a_value_outside_the_set_is_an_alarm(source, field, good, bad):
    spec = BY_ID[source]
    assert contracts.value_findings(spec, {field: good}) == []
    f = contracts.value_findings(spec, {field: bad})
    assert len(f) == 1 and f[0].level == "alarm" and field in f[0].text


def test_a_blank_value_is_not_a_violation_but_an_empty_answer_is():
    spec = BY_ID["cook.address_points"]
    assert contracts.value_findings(spec, {"st_predir": ("", "NORTH")}) == []
    assert contracts.value_findings(spec, {"st_predir": ()})[0].text.endswith("no values came back")


def test_many_bad_values_are_summarized():
    f = contracts.value_findings(BY_ID["chi.zoning.districts"], {"ZONE_CLASS": tuple(f"Q{i}" for i in range(9))})
    assert "and 4 more" in f[0].text


# --- renamed fields, renamed layers, error bodies --------------------------------------------------------

def test_a_renamed_field_is_an_error():
    spec = replace(BY_ID["chi.zoning.districts"], contract=Contract(required_fields=("ZONE_CLASS", "CLERK_DOCNO")))
    s = evaluate(spec, ProbeResult(published=TODAY, fields=("ZONE_CLASS", "CLERK_DOC_NUMBER")), TODAY)
    assert s.state == "error" and "CLERK_DOCNO" in s.reason


def test_a_layer_whose_name_changed_is_an_error():
    """Layer 5 is "Landmark Boundaries". If the City renumbers layers so 5 is something else, we'd read the wrong thing."""
    spec = BY_ID["chi.zoning.overlay.landmark_building"]
    assert spec.contract.layer_name == "Landmark Boundaries"
    s = evaluate(spec, ProbeResult(layer_name="Landmark Buildings", count=412), TODAY)
    assert s.state == "error" and "Landmark Buildings" in s.reason


def test_a_200_with_an_error_body_is_an_error_for_value_reads_too():
    with pytest.raises(ProbeError) as e:
        probes.parse_distinct(fx("arcgis_error_200.json"), "ZONE_CLASS", "distinct ZONE_CLASS")
    assert e.value.kind == "service"


def test_the_fields_read_contract_flags_t68z_cikk():
    """demographics.py read poverty, rent and tenure columns that t68z-cikk never had. The live columns are
    recorded; the old reads fail the contract that the module's own fields now feed."""
    live = tuple(fx("t68z-cikk_columns.json")["columns"])
    read_in_2026_10_20 = ("community_area", "below_poverty_level", "owner_occupied_housing_units",
                          "median_gross_rent", "population_25_years_and_over", "total_population")
    spec = replace(BY_ID["chi.acs_community_area"], contract=Contract(required_fields=read_in_2026_10_20))
    s = evaluate(spec, ProbeResult(content=TODAY, content_year=2024, reference_year=2024, fields=live), TODAY)
    assert s.state == "error"
    for gone in ("below_poverty_level", "owner_occupied_housing_units", "median_gross_rent", "population_25_years_and_over"):
        assert gone in s.reason
    # what the module reads today is all there
    today_spec = BY_ID["chi.acs_community_area"]
    ok = evaluate(today_spec, ProbeResult(content=TODAY, content_year=2024, reference_year=2024, fields=live), TODAY)
    assert "missing field" not in ok.reason


# --- the generated fields-read file ----------------------------------------------------------------------

def test_fields_read_names_only_columns_the_module_still_mentions():
    """The file is generated from the code. If a column was dropped from a module, its entry is stale: regenerate."""
    data = json.loads(FIELDS_READ_PATH.read_text())
    assert data, "fields_read.json is empty"
    for sid, cols in data.items():
        spec = BY_ID[sid]
        assert spec.kind == "socrata", sid
        words: set[str] = set()
        for path in contracts.reader_modules(spec):
            words |= contracts.module_words(path)
        stale = [c for c in cols if c not in words]
        assert not stale, f"{sid}: {stale} no longer read by its modules (run contracts --scan --write)"


def test_the_registry_carries_every_fields_read_entry():
    for sid, cols in load_fields_read().items():
        have = set(BY_ID[sid].contract.required_fields)
        assert set(cols) <= have, sid


def test_every_socrata_source_with_a_reading_module_has_a_fields_read_entry():
    """A new Socrata source whose module reads columns must get a contract (run --scan --write)."""
    entries = load_fields_read()
    without = []
    for s in SOURCES:
        if s.kind != "socrata" or s.retired or s.id in entries:
            continue
        without.append(s.id)
    # sources whose module names no column of the dataset: the community-area boundary set and the enterprise zones
    assert set(without) <= {"chi.community_areas", "chi.enterprise_zones", "chi.socioeconomic_2008_2012"} | {
        s.id for s in SOURCES if s.kind == "socrata" and s.retired}, without


def test_fixed_size_sets_have_exact_count_bands():
    assert BY_ID["chi.wards"].contract.count_band == (50, 50)
    assert BY_ID["chi.community_areas"].contract.count_band == (77, 77)
    s = evaluate(BY_ID["chi.wards"], ProbeResult(published=TODAY, count=51), TODAY)
    assert s.state == "alarm" and "51" in s.reason


# --- probes: counts and distinct values over a mock transport -----------------------------------------------

def test_parse_socrata_count_and_distinct():
    assert probes.parse_socrata_count([{"n": "50"}]) == 50
    with pytest.raises(ProbeError):
        probes.parse_socrata_count([])
    assert probes.parse_distinct([{"st_predir": "NORTH", "n": "1"}, {"n": "546"}, {"st_predir": "WEST"}], "st_predir") == ("NORTH", "WEST")
    assert probes.parse_distinct(fx("arcgis_distinct_landmark.json"), "LANDMARK") == ("Y",)


def _run(spec, handler):
    async def go():
        client, total = probes.make_client(httpx.MockTransport(handler))
        ctx = probes.ProbeContext(client=client, sem=asyncio.Semaphore(4), today=TODAY)
        try:
            return await probes.run_probe(spec, ctx), total()
        finally:
            await client.aclose()

    return asyncio.run(go())


def test_the_arcgis_probe_reads_distinct_values_for_a_value_contract():
    spec = BY_ID["chi.zoning.overlay.historic_district"]

    def handle(req):
        url = str(req.url)
        if "returnDistinctValues" in url:
            return httpx.Response(200, json=fx("arcgis_distinct_landmark.json"))
        if "returnCountOnly" in url:
            return httpx.Response(200, json={"count": 70})
        return httpx.Response(200, json={"name": "Historic Districts", "fields": [{"name": "LANDMARK"}]})

    res, n = _run(spec, handle)
    assert res.error is None and res.values == {"LANDMARK": ("Y",)} and res.count == 70 and n == 3


def test_the_socrata_probe_reads_count_and_distinct_values():
    spec = BY_ID["cook.address_points"]

    def handle(req):
        url = str(req.url)
        if "%24group" in url or "$group" in url:
            return httpx.Response(200, json=[{"st_predir": "NORTH"}, {"st_predir": "SOUTH"}])
        return httpx.Response(200, json={"rowsUpdatedAt": 1712534400, "columns": [{"fieldName": "pin"}, {"fieldName": "st_predir"}]})

    res, _ = _run(spec, handle)
    assert res.error is None and res.values == {"st_predir": ("NORTH", "SOUTH")}
    s = evaluate(spec, res, TODAY)
    assert "unexpected" not in s.reason
