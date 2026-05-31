from backend.assembler import assemble_context
from backend.config import get_settings
from backend.models import CodeChunk, Location, RetrievalPlan

_settings = get_settings()
TOP_CRIME_TYPES = _settings.top_crime_types
TOP_311_TYPES = _settings.top_311_types
TOP_CHUNKS = _settings.top_chunks


def _plan(**kwargs) -> RetrievalPlan:
    loc = Location(
        raw="West Town",
        type="community_area",
        resolved_community_area=24,
        resolved_community_area_name="West Town",
    )
    defaults = dict(
        sources=["crime_api"],
        location=loc,
        intent="neighborhood_overview",
        time_range_days=90,
        requires_disclaimer=False,
    )
    defaults.update(kwargs)
    return RetrievalPlan(**defaults)


def test_crime_caps_to_top_5_types():
    rows = [
        {"primary_type": f"TYPE_{i}", "count": str(100 - i), "arrests": "5"}
        for i in range(20)
    ]
    ctx = assemble_context(plan=_plan(), crime_rows=rows)
    assert ctx.crime_last_90d is not None
    assert len(ctx.crime_last_90d.by_type) == TOP_CRIME_TYPES
    assert ctx.crime_last_90d.total == sum(100 - i for i in range(20))


def test_crime_arrest_rate_computed():
    rows = [
        {"primary_type": "THEFT", "count": "80", "arrests": "10"},
        {"primary_type": "BATTERY", "count": "20", "arrests": "10"},
    ]
    ctx = assemble_context(plan=_plan(), crime_rows=rows)
    assert ctx.crime_last_90d.arrest_rate == 0.2


def test_data_lag_note_present_when_crime_present():
    rows = [{"primary_type": "THEFT", "count": "5", "arrests": "1"}]
    ctx = assemble_context(plan=_plan(), crime_rows=rows)
    assert ctx.data_lag_note is not None
    assert "7 days" in ctx.data_lag_note


def test_data_lag_note_absent_when_no_crime():
    ctx = assemble_context(plan=_plan())
    assert ctx.data_lag_note is None
    assert ctx.crime_last_90d is None


def test_three11_filters_open_dup():
    rows = [
        {"owner_department": "S&S", "sr_type": "Open - Dup", "count": "999"},
        {"owner_department": "S&S", "sr_type": "Pothole in Street", "count": "20"},
        {"owner_department": "CDOT", "sr_type": "Graffiti Removal", "count": "10"},
    ]
    ctx = assemble_context(plan=_plan(), three11_rows=rows)
    assert ctx.open_311_requests is not None
    assert ctx.open_311_requests.total == 30
    assert "Open - Dup" not in ctx.open_311_requests.top_types


def test_three11_caps_types():
    rows = [
        {"owner_department": "D", "sr_type": f"Type {i}", "count": "1"}
        for i in range(30)
    ]
    ctx = assemble_context(plan=_plan(), three11_rows=rows)
    assert len(ctx.open_311_requests.top_types) == TOP_311_TYPES


def test_code_chunks_capped_and_sorted():
    chunks = [
        CodeChunk(
            text="x",
            source_document="Chicago Municipal Code",
            section=f"17-{i}-{i}",
            section_title=f"Section {i}",
            score=i / 10.0,
        )
        for i in range(20)
    ]
    ctx = assemble_context(plan=_plan(), code_chunks=chunks)
    assert len(ctx.code_chunks) == TOP_CHUNKS
    scores = [c.score for c in ctx.code_chunks]
    assert scores == sorted(scores, reverse=True)


def test_disclaimer_flag_propagates():
    plan = _plan(requires_disclaimer=True)
    ctx = assemble_context(plan=plan)
    assert ctx.requires_disclaimer is True


def test_permits_aggregate_estimated_cost():
    rows = [
        {"work_description": "New construction", "estimated_cost": "100000"},
        {"work_description": "Renovation", "estimated_cost": "50000"},
        {"work_description": "Reno", "estimated_cost": None},
    ]
    ctx = assemble_context(plan=_plan(), permit_rows=rows)
    assert ctx.permits is not None
    assert ctx.permits.total == 3
    assert ctx.permits.total_estimated_cost == 150000.0


def test_violations_count_open():
    rows = [
        {"violation_description": "Plumbing", "violation_status": "OPEN"},
        {"violation_description": "Electrical", "violation_status": "COMPLIED"},
        {"violation_description": "Plumbing", "violation_status": "OPEN"},
    ]
    ctx = assemble_context(plan=_plan(), violation_rows=rows)
    assert ctx.violations.open_count == 2
    assert ctx.violations.total == 3


def test_zoning_info_attached_when_present():
    zoning = {"zone_class": "B2", "zone_type": 1, "ordinance_num": "12345"}
    ctx = assemble_context(plan=_plan(), zoning_info=zoning)
    assert ctx.parcel_zoning is not None
    assert ctx.parcel_zoning.zone_class == "B2"
    assert "ZoningMapWeb" in ctx.parcel_zoning.zoning_map_url


def test_zoning_info_none_when_absent():
    ctx = assemble_context(plan=_plan())
    assert ctx.parcel_zoning is None


def test_zoning_info_none_when_empty_zone_class():
    zoning = {"zone_class": None, "zone_type": "B"}
    ctx = assemble_context(plan=_plan(), zoning_info=zoning)
    assert ctx.parcel_zoning is None
