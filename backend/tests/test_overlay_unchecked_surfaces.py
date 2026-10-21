"""WS6 M7a: an overlay layer the City map couldn't answer reads "couldn't check", never "No".

The retrieval tri-state itself is in test_regulatory_overlays.py; these pin the
surfaces: partial_failures (Profile, chat, report) and the report's status grid.
"""



from backend.main import _domain_data_gaps
from backend.models import ContextObject, PropertySummary, RegulatorySummary, ReportData

GAP = "landmark designation (City zoning map didn't answer)"


def _render(report: ReportData) -> str:
    """Render the real PDF template to HTML (GIS-independent)."""
    from backend.main import render_report_html

    return render_report_html(report, report.language, report_date="October 20, 2026")


def _status_cell(html: str, label: str) -> str:
    dt = html.index(f"<dt>{label}</dt>")
    return html[html.index("<dd>", dt):html.index("</dd>", dt)]


def test_domain_gaps_merge_from_every_summary():
    results = {
        "property": PropertySummary(data_gaps=["property assessments"]),
        "regulatory": RegulatorySummary(unchecked_overlays=["landmark_building"], data_gaps=[GAP]),
        "zoning": None,
    }
    assert _domain_data_gaps(results, ("property", "regulatory")) == ["property assessments", GAP]
    assert _domain_data_gaps(results, ("regulatory",)) == [GAP]
    assert _domain_data_gaps({"regulatory": None}, ("regulatory",)) == []


def test_report_says_couldnt_check_instead_of_no():
    reg = RegulatorySummary(unchecked_overlays=["landmark_building"], data_gaps=[GAP])
    html = _render(ReportData(context=ContextObject(regulatory=reg), partial_failures=[GAP]))

    assert "Couldn&#39;t check today" in _status_cell(html, "Chicago Landmark District")
    assert GAP.replace("'", "&#39;") in html
    # No "no overlays detected" claim while a layer is unknown.
    assert "No overlay or special districts detected" not in html
    # Layers that WERE checked still read plainly.
    assert "Couldn&#39;t check" not in _status_cell(html, "National Register District")


def test_report_unchanged_when_everything_was_checked():
    html = _render(ReportData(context=ContextObject(regulatory=RegulatorySummary())))
    assert "Couldn&#39;t check" not in html
    assert "No overlay or special districts detected" in html
