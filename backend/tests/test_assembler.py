from backend.assembler import assemble_context, _categorize_violation, _interpret_tax_class
from backend.config import get_settings
from backend.models import (
    CodeChunk,
    DemographicsSummary,
    IncentivesSummary,
    Location,
    NeighborhoodSummary,
    PropertySummary,
    RegulatorySummary,
    RetrievalPlan,
    TransitAccess,
)

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
    data = {
        "grouped": [
            {"permit_type": "PERMIT - NEW CONSTRUCTION", "count": "1", "total_cost": "100000"},
            {"permit_type": "PERMIT - RENOVATION/ALTERATION", "count": "2", "total_cost": "50000"},
        ],
        "detail": [
            {"work_description": "New construction"},
            {"work_description": "Renovation"},
            {"work_description": "Reno"},
        ],
    }
    ctx = assemble_context(plan=_plan(), permit_data=data)
    assert ctx.permits is not None
    assert ctx.permits.total == 3
    assert ctx.permits.total_estimated_cost == 150000.0
    assert ctx.permits.capped is False


def test_violations_count_open():
    data = {
        "status_counts": [
            {"violation_status": "OPEN", "count": "2"},
            {"violation_status": "COMPLIED", "count": "1"},
        ],
        "detail": [
            {"violation_description": "Plumbing", "violation_status": "OPEN"},
            {"violation_description": "Electrical", "violation_status": "COMPLIED"},
            {"violation_description": "Plumbing", "violation_status": "OPEN"},
        ],
    }
    ctx = assemble_context(plan=_plan(), violation_data=data)
    assert ctx.violations.open_count == 2
    assert ctx.violations.total == 3
    assert ctx.violations.capped is False


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


def test_regulatory_summary_attached_when_provided():
    reg = RegulatorySummary(
        in_landmark_district=True,
        flood_zone="AE",
        in_special_flood_hazard=True,
    )
    ctx = assemble_context(plan=_plan(), regulatory_summary=reg)
    assert ctx.regulatory is not None
    assert ctx.regulatory.in_landmark_district is True
    assert ctx.regulatory.flood_zone == "AE"


def test_regulatory_summary_none_when_absent():
    ctx = assemble_context(plan=_plan())
    assert ctx.regulatory is None


def test_neighborhood_summary_attached_when_provided():
    ns = NeighborhoodSummary(
        demographics=DemographicsSummary(community_area=24, population=87781),
        transit=TransitAccess(
            nearest_cta_rail="Damen",
            cta_rail_distance_mi=0.3,
            tod_eligible=True,
            tod_type="CTA rail",
        ),
    )
    ctx = assemble_context(plan=_plan(), neighborhood_summary=ns)
    assert ctx.neighborhood is not None
    assert ctx.neighborhood.demographics.population == 87781
    assert ctx.neighborhood.transit.nearest_cta_rail == "Damen"


def test_neighborhood_summary_none_when_absent():
    ctx = assemble_context(plan=_plan())
    assert ctx.neighborhood is None


class TestTaxIncentiveClassInterpretation:
    def test_class_6b(self):
        code, desc = _interpret_tax_class("6b")
        assert code == "6B"
        assert "rehabilitation" in desc.lower()

    def test_class_7a(self):
        code, desc = _interpret_tax_class("7a")
        assert code == "7A"
        assert "economically disadvantaged" in desc.lower()

    def test_class_8(self):
        code, desc = _interpret_tax_class("8")
        assert code == "8"
        assert "industrial" in desc.lower()

    def test_standard_class_returns_none(self):
        code, desc = _interpret_tax_class("2-99")
        assert code is None
        assert desc is None

    def test_none_input(self):
        code, desc = _interpret_tax_class(None)
        assert code is None
        assert desc is None

    def test_empty_string(self):
        code, desc = _interpret_tax_class("")
        assert code is None
        assert desc is None

    def test_case_insensitive(self):
        code, _ = _interpret_tax_class("6B")
        assert code == "6B"


def test_tax_incentive_enriches_incentives_summary():
    prop = PropertySummary(pin14="12345678901234", bldg_class="6b")
    inc = IncentivesSummary(in_tif_district=True, tif_name="Test TIF")
    ctx = assemble_context(
        plan=_plan(),
        property_summary=prop,
        incentives_summary=inc,
    )
    assert ctx.incentives is not None
    assert ctx.incentives.property_tax_class == "6B"
    assert ctx.incentives.tax_incentive_description is not None
    assert ctx.incentives.in_tif_district is True


def test_tax_incentive_creates_summary_when_no_incentives():
    prop = PropertySummary(pin14="12345678901234", bldg_class="7a")
    ctx = assemble_context(plan=_plan(), property_summary=prop)
    assert ctx.incentives is not None
    assert ctx.incentives.property_tax_class == "7A"


def test_no_tax_incentive_for_standard_class():
    prop = PropertySummary(pin14="12345678901234", bldg_class="2-99")
    ctx = assemble_context(plan=_plan(), property_summary=prop)
    assert ctx.incentives is None


class TestViolationCategorization:
    def test_keyword_match(self):
        assert _categorize_violation("REPAIR EXTERIOR WALL") == "Exterior Structure"

    def test_elevator_abbreviation(self):
        assert _categorize_violation("MAINTAIN OR REPAIR ELECT ELEVA") == "Elevator/Escalator"

    def test_code_prefix_elevator(self):
        assert _categorize_violation("SOME DESCRIPTION", "EV1110") == "Elevator/Escalator"

    def test_code_prefix_boiler(self):
        assert _categorize_violation("SOME DESCRIPTION", "BR1010") == "Boiler/Mechanical"

    def test_keyword_overrides_when_no_code(self):
        assert _categorize_violation("REPAIR PORCH SYSTEM") == "Porch/Deck"

    def test_unknown_falls_to_other(self):
        assert _categorize_violation("MISCELLANEOUS VIOLATION") == "Other"

    def test_fire_escape(self):
        assert _categorize_violation("FIRE ESCAPE REPAIR") == "Fire Safety"

    def test_code_used_with_violation_data(self):
        data = {
            "status_counts": [{"violation_status": "OPEN", "count": "1"}],
            "detail": [
                {
                    "violation_description": "MAINTAIN OR REPAIR ELECT ELEVA",
                    "violation_code": "EV1110",
                    "violation_status": "OPEN",
                },
            ],
        }
        ctx = assemble_context(plan=_plan(), violation_data=data)
        assert "Elevator/Escalator" in ctx.violations.by_category
