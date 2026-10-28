"""City Clerk client (WS1 M1), offline. Fixtures in fixtures/clerk/ are trimmed copies
of live responses recorded 2026-10-21; httpx.MockTransport serves them, so nothing here
touches the network."""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import httpx
import pytest

from backend.retrieval import clerk

FIX = Path(__file__).resolve().parent / "fixtures" / "clerk"


def _json(name: str):
    return json.loads((FIX / name).read_text())


@pytest.fixture(autouse=True)
def _no_waiting(monkeypatch):
    async def instant(_s):
        return None
    monkeypatch.setattr(clerk, "_sleep", instant)


class Recorder:
    """A MockTransport handler that records requests and replays canned responses."""

    def __init__(self, respond):
        self.respond = respond
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return self.respond(request, len(self.requests))

    def client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(transport=httpx.MockTransport(self))

    def params(self, i: int = 0) -> dict[str, str]:
        return {k: v[0] for k, v in parse_qs(urlparse(str(self.requests[i].url)).query).items()}


def _serve(body, status: int = 200):
    def respond(_req, _n):
        if isinstance(body, str):
            return httpx.Response(status, text=body, headers={"content-type": "text/plain"})
        return httpx.Response(status, json=body)
    return Recorder(respond)


# --- the acceptance numbers, on the recorded data -----------------------------------------

async def test_passed_code_amendments_since_the_vintage():
    rec = _serve(_json("code_amendments_since_2026-03-18.json"))
    matters = await clerk.passed_since(date(2026, 3, 18), client=rec.client())

    assert len(matters) == 97  # 100 final: 2 failed to pass, 1 vetoed
    assert all(m.passed and m.passed_on > date(2026, 3, 18) for m in matters)
    assert [m.final_action_at for m in matters] == sorted(m.final_action_at for m in matters)
    # Subcategories ("... | 4-60-023 Package Goods") are code amendments too.
    assert sum("|" in m.category for m in matters) == 41
    # "Signed" is passed: the omnibus building-code amendment ends that way.
    assert any(m.record_number == "SO2026-0024930" and m.sub_status == "Signed" for m in matters)

    flt = rec.params()["filter"]
    assert "finalActionDate ge 2026-03-19T05:00:00Z" in flt  # midnight after the vintage, Chicago time
    assert "matterCategory ge 'MUNICIPAL CODE AMENDMENTS' and matterCategory lt 'MUNICIPAL CODE AMENDMENTT'" in flt


async def test_the_16_title17_amendments():
    rec = _serve(_json("code_amendments_since_2026-03-18.json"))
    got = await clerk.passed_title17_amendments(date(2026, 3, 18), client=rec.client())

    assert {a.record_number for a in got} == {
        "O2025-0018447", "O2026-0024064", "SO2025-0017570", "SO2026-0024923", "O2026-0025414",
        "SO2026-0024930", "O2026-0025429", "O2026-0025463", "O2026-0025464", "O2026-0026278",
        "SO2026-0026276", "O2026-0026042", "SO2026-0024882", "SO2026-0027187", "SO2026-0025391",
        "SO2026-0028463",
    }
    by = {a.record_number: a for a in got}
    assert by["SO2026-0024930"].kind == "omnibus"
    assert by["O2026-0026042"].kind == "map_designation"  # Lawrence Ave pedestrian-street removal
    assert by["SO2026-0025391"].touched_sections == ["17-3", "17-3-0600"]
    assert by["O2026-0025414"].touched_sections == ["17-12-1105-B"]
    assert by["SO2026-0025391"].passed_date == date(2026, 10, 14)
    assert all(a.sections_confidence == "title" and a.url.startswith(clerk.PUBLIC_MATTER_URL[:40]) for a in got)


def test_a_mention_of_transit_is_not_title17():
    # O2026-0026413 amends Chapter 9-64 and mentions the CTA; it is not a zoning change.
    assert not clerk.touches_title17("Amendment of Municipal Code Chapter 9-64 to permit vehicles ... beneath Chicago Transit Authority tracks")
    assert clerk.touches_title17("Amendment of Municipal Code Titles 2, 14A, 17 and 18 regarding various provisions")
    assert clerk.touches_title17("Amendment of Municipal Code Section 17-9-0109A to require special use approval")


# --- dates ------------------------------------------------------------------------------------

def _row(**over):
    row = {
        "matterId": "X", "recordNumber": "O2026-0000001", "status": "90-Final", "subStatus": "Passed",
        "matterCategory": "MUNICIPAL CODE AMENDMENTS", "title": "t", "finalActionDate": "2026-03-18T15:00:00+00:00",
        "recordCreateDate": "2026-03-01T15:00:00+00:00", "lastPublicationDate": "2026-03-19T15:00:00+00:00",
    }
    row.update(over)
    return row


@pytest.mark.parametrize("stamp, chicago_day", [
    ("2026-03-18T15:00:00+00:00", date(2026, 3, 18)),  # final action: 10 am Chicago
    ("2026-03-18T05:00:00+00:00", date(2026, 3, 18)),  # action dates: Chicago midnight
    ("2026-03-19T04:30:00+00:00", date(2026, 3, 18)),  # 11:30 pm Chicago, still the 18th
])
def test_dates_compare_in_chicago(stamp, chicago_day):
    assert clerk.ClerkMatter.from_api(_row(finalActionDate=stamp)).passed_on == chicago_day


async def test_passed_on_the_vintage_day_is_not_since_it():
    page = {"data": [_row(finalActionDate="2026-03-19T04:30:00+00:00")], "meta": {"count": 1}}
    assert await clerk.passed_since(date(2026, 3, 18), client=_serve(page).client()) == []


async def test_latest_record_date_ignores_future_introduction_dates():
    rec = _serve(_json("recent_window_2026-10-18.json"))
    got = await clerk.latest_record_date(now=datetime(2026, 10, 21, tzinfo=timezone.utc), client=rec.client())
    assert got == datetime(2026, 10, 20, 22, 1, 7, tzinfo=timezone.utc)
    assert "recordCreateDate gt 2026-10-14T00:00:00Z" == rec.params()["filter"]
    assert "sort" not in rec.params()  # the server rejects sort=recordCreateDate


async def test_no_recent_records_is_a_broken_feed_not_a_quiet_council():
    rec = _serve(_json("empty_page.json"))
    with pytest.raises(clerk.ClerkUnavailable):
        await clerk.latest_record_date(client=rec.client())
    assert len(rec.requests) == 2  # 7 days, then 30


# --- contract ---------------------------------------------------------------------------------

def test_a_row_missing_a_required_field_is_contract_drift():
    row = _row()
    del row["recordCreateDate"]
    with pytest.raises(clerk.ClerkUnavailable):
        clerk.ClerkMatter.from_api(row)


def test_unknown_fields_are_ignored_and_optional_ones_may_be_missing():
    m = clerk.ClerkMatter.from_api(_row(somethingNew={"x": 1}, introductionDate=None))
    assert m.attachments == [] and m.actions == [] and m.introduced_at is None


def test_every_recorded_final_substatus_is_known():
    rows = _json("code_amendments_since_2026-03-18.json")["data"]
    assert {r["subStatus"] for r in rows} <= clerk.KNOWN_FINAL_SUBSTATUSES


async def test_a_bad_shape_raises():
    with pytest.raises(clerk.ClerkUnavailable):
        await clerk.search_matters("x", client=_serve({"items": []}).client())


# --- substitutes ------------------------------------------------------------------------------

def test_substitute_rezoning_picks_the_so_final_ordinance():
    m = clerk.ClerkMatter.from_api(_json("matter_SO2026-0026077.json"))
    assert m.is_substitute and m.original_record_number == "O2026-0026077"
    assert len(m.attachments) == 6 and len(m.actions) == 4
    assert m.legislation_pdf().file_name == "SO2026-0026077 Final Ordinance.pdf"


def test_substitute_without_final_in_the_name_picks_the_so_pdf():
    m = clerk.ClerkMatter.from_api(_json("matter_SO2026-0025391.json"))
    assert m.legislation_pdf().file_name == "SO2026-0025391.pdf"  # TOD Streets: not "O... Ordinance.pdf"


def test_an_original_ordinance_picks_its_legislation_pdf():
    m = clerk.ClerkMatter.from_api(_row(attachments=[
        {"fileName": "O2026-1 Application.pdf", "path": "u1", "attachmentType": "Miscellaneous"},
        {"fileName": "O2026-1 Ordinance.pdf", "path": "u2", "attachmentType": "Legislation"},
    ]))
    assert not m.is_substitute and m.legislation_pdf().url == "u2"


# --- pagination and failures ------------------------------------------------------------------

def _paged(rows: list[dict], page: int, fail_at: int | None = None, short_at: int | None = None):
    def respond(req, n):
        skip = int(parse_qs(urlparse(str(req.url)).query)["skip"][0])
        if fail_at is not None and skip >= fail_at:
            return httpx.Response(503)
        chunk = [] if short_at is not None and skip >= short_at else rows[skip:skip + page]
        return httpx.Response(200, json={"data": chunk, "meta": {"count": len(rows)}})
    return Recorder(respond)


async def test_pagination_stops_at_the_count():
    rows = [_row(recordNumber=f"O2026-{i:07d}") for i in range(7)]
    rec = _paged(rows, page=3)
    got = [m.record_number async for m in clerk.iter_matters("f", client=rec.client())]
    assert len(got) == 7 and len(rec.requests) == 3
    assert [rec.params(i)["skip"] for i in range(3)] == ["0", "3", "6"]


async def test_a_failed_page_mid_pagination_raises_instead_of_returning_part():
    rows = [_row(recordNumber=f"O2026-{i:07d}", finalActionDate="2026-04-01T15:00:00+00:00") for i in range(7)]
    with pytest.raises(clerk.ClerkUnavailable):
        await clerk.passed_since(date(2026, 3, 18), client=_paged(rows, page=3, fail_at=3).client())


async def test_rate_limit_is_retried_and_honors_bounded_retry_after(monkeypatch):
    waits: list[float] = []

    async def record_wait(seconds: float):
        waits.append(seconds)

    monkeypatch.setattr(clerk, "_sleep", record_wait)

    def respond(_request, n):
        if n == 1:
            return httpx.Response(429, headers={"Retry-After": "7"})
        return httpx.Response(200, json={"data": [_row()], "meta": {"count": 1}})

    rec = Recorder(respond)
    rows, count = await clerk.search_matters("x", client=rec.client())
    assert count == 1 and len(rows) == 1
    assert len(rec.requests) == 2 and waits == [7.0]


async def test_rate_limit_with_unbounded_retry_after_uses_safe_fallback(monkeypatch):
    waits: list[float] = []

    async def record_wait(seconds: float):
        waits.append(seconds)

    monkeypatch.setattr(clerk, "_sleep", record_wait)
    rec = _serve("busy", status=429)
    with pytest.raises(clerk.ClerkUnavailable, match="failed after 3 attempts"):
        await clerk.search_matters("x", client=rec.client())
    assert waits == [clerk._RATE_LIMIT_BACKOFF_S, clerk._RATE_LIMIT_BACKOFF_S]


async def test_a_short_page_raises():
    rows = [_row(recordNumber=f"O2026-{i:07d}") for i in range(7)]
    with pytest.raises(clerk.ClerkUnavailable):
        [m async for m in clerk.iter_matters("f", client=_paged(rows, page=3, short_at=3).client())]


async def test_a_400_is_our_query_and_is_not_retried():
    rec = _serve((FIX / "bad_filter_400.txt").read_text(), status=400)
    with pytest.raises(clerk.ClerkQueryError, match="serch and filter"):
        await clerk.search_matters("bogus", client=rec.client())
    assert len(rec.requests) == 1


async def test_a_503_is_retried_three_times_then_unavailable():
    rec = _serve({}, status=503)
    with pytest.raises(clerk.ClerkUnavailable):
        await clerk.search_matters("f", client=rec.client())
    assert len(rec.requests) == 3


async def test_a_transient_503_recovers():
    page = _json("empty_page.json")
    rec = Recorder(lambda _req, n: httpx.Response(503) if n == 1 else httpx.Response(200, json=page))
    assert await clerk.search_matters("f", client=rec.client()) == ([], 0)


async def test_a_network_error_never_becomes_an_empty_list():
    def respond(req, _n):
        raise httpx.ConnectError("down", request=req)
    with pytest.raises(clerk.ClerkUnavailable):
        await clerk.passed_since(date(2026, 3, 18), client=Recorder(respond).client())


async def test_a_missing_record_is_none():
    rec = _serve("", status=404)
    assert await clerk.get_matter_by_record("O2099-0000001", client=rec.client()) is None


async def test_record_lookup_parses_and_caches():
    rec = _serve(_json("matter_SO2026-0025391.json"))
    first = await clerk.get_matter_by_record("SO2026-0025391", client=rec.client())
    again = await clerk.get_matter_by_record("SO2026-0025391", client=rec.client())
    assert first is again and len(rec.requests) == 1
    assert rec.requests[0].url.path == "/matter/recordNumber/SO2026-0025391"


# --- filter helpers ---------------------------------------------------------------------------

def test_odata_str_escapes_quotes():
    assert clerk.odata_str("O'Hare") == "'O''Hare'"


def test_category_filter_covers_subcategories_and_ors_several():
    one = clerk.category_filter(["ZONING RECLASSIFICATIONS"])
    assert one == "(matterCategory ge 'ZONING RECLASSIFICATIONS' and matterCategory lt 'ZONING RECLASSIFICATIONT')"
    two = clerk.category_filter([clerk.CODE_AMENDMENTS, clerk.ZONING_RECLASSIFICATIONS])
    assert two.startswith("((") and " or " in two
