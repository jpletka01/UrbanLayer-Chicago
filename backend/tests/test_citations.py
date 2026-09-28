from backend.citations import KNOWN_DATA_MARKERS, citation_problems, data_sources_present
from backend.models import ContextObject, CrimeSummary


def test_backed_citations_pass():
    assert citation_problems("See [1] and [2]; 40 thefts [data:crime].", 2, {"crime"}) == []


def test_out_of_range_code_citation():
    assert citation_problems("Per [3].", 2, set()) == [
        "[3] cites a code chunk that wasn't retrieved (2 available)",
    ]


def test_zero_is_out_of_range():
    assert citation_problems("[0]", 5, set())


def test_data_marker_without_data():
    assert citation_problems("[data:311]", 0, {"crime"}) == [
        "[data:311] cited but that data wasn't in the context",
    ]


def test_unknown_data_marker():
    assert citation_problems("[data:weather]", 0, set()) == ["[data:weather] is not a known data source"]


def test_repeated_markers_reported_once():
    assert len(citation_problems("[9] [9] [9]", 1, set())) == 1


def test_data_sources_present_reads_models_and_dicts():
    ctx = ContextObject(crime_last_90d=CrimeSummary(total=1, arrest_rate=0.0, by_type={}))
    assert data_sources_present(ctx) == {"crime"}
    assert data_sources_present({"permits": {"total": 3}, "violations": None}) == {"permits"}


def test_known_markers_match_the_prompt():
    # Every [data:x] the synthesizer prompt asks for must be recognised here.
    import re

    from backend.prompts import SYNTHESIZER_SYSTEM

    prompted = set(re.findall(r"\[data:([a-z0-9_]+)\]", SYNTHESIZER_SYSTEM))
    assert prompted <= KNOWN_DATA_MARKERS
