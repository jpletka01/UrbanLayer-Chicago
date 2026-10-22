"""WS6 M8: a purchase keeps the first report it rendered, as sold, and every later download says it is an update.

Jack's policy (2026-10-20): the original PDF plus an updated copy, free and unlimited for now. The first
render of a purchase is stored once, byte for byte, under a hash; ``copy=original`` serves exactly that;
every other download is a live render with today's data, labeled once an original exists. Every render keeps
its facts and data dates. Account deletion removes the PDFs and the render rows, never the purchase ledger.
"""

from __future__ import annotations

import hashlib
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
import pytest_asyncio

import backend.main as main_mod
from backend import db
from backend.main import app, render_report_html, require_auth
from backend.models import ContextObject, ReportData, ZoningSummary
from backend.report_builder import _apply_mock_overrides

PIN = "14313320180000"
LAT, LON = 41.91, -87.68


@pytest_asyncio.fixture
async def world(tmp_path):
    """A real database, a real report store (tmp), three users: a buyer, a premium subscriber and an admin."""
    settings = MagicMock()
    settings.db_path = tmp_path / "t.db"
    settings.report_store_dir = tmp_path / "reports"
    with patch("backend.db.get_settings", return_value=settings):
        await db.init_db()
        await db.upsert_user("buyer", "b@x.com", "Buyer", None, "g1")
        await db.upsert_user("pro", "p@x.com", "Pro", None, "g2")
        await db.update_user_tier("pro", "premium")
        await db.upsert_user("boss", "a@x.com", "Admin", None, "g3")
        await db.update_user_tier("boss", "admin")
        sid = "cs_test_1"
        await db.save_report_purchase("buyer", sid, "1601 N Milwaukee Ave", LAT, LON, pin=PIN)
        await db.complete_report_purchase(sid, "pi_1")
        yield {"root": tmp_path / "reports", "settings": settings}
        await db.close_db()


def make_report() -> ReportData:
    ctx = ContextObject(resolved_address="1601 N Milwaukee Ave", parcel_pin=PIN, parcel_zoning=ZoningSummary(zone_class="B3-2", map_updated="2021-12-15"))
    return _apply_mock_overrides(ReportData(address="1601 N Milwaukee Ave", lat=LAT, lon=LON, context=ctx, resolved_pin=PIN, resolved_confidence="authoritative"))


class Renderer:
    """Stands in for the data fetch, the HTML and the PDF: each render returns the next bytes, so a served original
    can be told from a fresh render."""

    def __init__(self):
        self.n = 0
        self.copy_of: list[str | None] = []

    async def fetch(self, *a, **k):
        return (make_report(), None, None)

    def html(self, report, language="en", report_date=None, copy_of=None):
        self.copy_of.append(copy_of)
        return "<html></html>"

    async def pdf(self, html, **k):
        self.n += 1
        return f"%PDF-1.4 render-{self.n}".encode()


async def get(user: dict, **params) -> httpx.Response:
    app.dependency_overrides[require_auth] = lambda: user
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as ac:
            return await ac.get("/api/report", params={"pin": PIN, **params})
    finally:
        app.dependency_overrides.pop(require_auth, None)


def patched(r: Renderer):
    from contextlib import ExitStack

    stack = ExitStack()
    stack.enter_context(patch.object(main_mod, "_resolve_location", new=AsyncMock(return_value=main_mod.ResolvedLocation(LAT, LON, "1601 N Milwaukee Ave", PIN, "authoritative"))))
    stack.enter_context(patch.object(main_mod, "_fetch_report_data", new=r.fetch))
    stack.enter_context(patch.object(main_mod, "render_report_html", new=r.html))
    stack.enter_context(patch("backend.report_render.render_pdf", new=r.pdf))
    return stack


BUYER = {"id": "buyer", "tier": "free", "email": "b@x.com"}
PRO = {"id": "pro", "tier": "premium", "email": "p@x.com"}
BOSS = {"id": "boss", "tier": "admin", "email": "a@x.com"}


async def renders(where: str = "1=1") -> list[dict]:
    cur = await db._get_db().execute(f"SELECT * FROM report_renders WHERE {where} ORDER BY id")
    return [dict(r) for r in await cur.fetchall()]


# --- the first render becomes the original ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_the_first_download_is_stored_as_the_original_and_labeled_as_such(world):
    r = Renderer()
    with patched(r):
        resp = await get(BUYER)
    assert resp.status_code == 200 and resp.content == b"%PDF-1.4 render-1" and resp.headers["x-report-copy"] == "original"
    assert r.copy_of == [None]  # the original carries no "updated copy" line
    (row,) = await renders()
    assert row["kind"] == "original" and row["purchase_id"] is not None and row["user_id"] == "buyer" and row["pin"] == PIN
    assert row["pdf_sha256"] == hashlib.sha256(resp.content).hexdigest() and row["pdf_bytes"] == len(resp.content)
    assert (world["root"] / row["pdf_path"]).read_bytes() == resp.content
    assert '"zone_class":"B3-2"' in row["facts_json"] and row["vintages_json"]


@pytest.mark.asyncio
async def test_a_second_download_is_a_live_render_labeled_as_an_updated_copy(world):
    r = Renderer()
    with patched(r):
        first = await get(BUYER)
        second = await get(BUYER)
    assert second.content == b"%PDF-1.4 render-2" and second.content != first.content and second.headers["x-report-copy"] == "updated"
    assert r.copy_of[0] is None and r.copy_of[1] is not None and len(r.copy_of[1]) == 10  # the day the first was generated
    kinds = [x["kind"] for x in await renders()]
    assert kinds == ["original", "updated"]
    updated = (await renders("kind = 'updated'"))[0]
    assert updated["pdf_path"] is None and updated["pdf_sha256"] is None  # only the original keeps its PDF
    assert updated["facts_json"] and updated["purchase_id"] == (await renders("kind = 'original'"))[0]["purchase_id"]


@pytest.mark.asyncio
async def test_copy_original_serves_exactly_the_stored_bytes_whatever_the_data_is_now(world):
    r = Renderer()
    with patched(r):
        first = await get(BUYER)
        await get(BUYER)                         # a newer render exists
        original = await get(BUYER, copy="original")
    assert original.content == first.content == b"%PDF-1.4 render-1"
    assert original.headers["x-report-copy"] == "original" and "_original.pdf" in original.headers["content-disposition"]
    assert r.n == 2  # serving the original rendered nothing


@pytest.mark.asyncio
async def test_copy_original_before_any_render_is_a_clear_404_and_renders_nothing(world):
    r = Renderer()
    with patched(r):
        resp = await get(BUYER, copy="original")
    assert resp.status_code == 404 and resp.json()["detail"] == {"error": "no_original"} and r.n == 0


@pytest.mark.asyncio
async def test_an_original_that_fails_its_hash_or_is_gone_is_never_served_as_one(world):
    r = Renderer()
    with patched(r):
        await get(BUYER)
        (row,) = await renders()
        f = world["root"] / row["pdf_path"]
        f.write_bytes(b"%PDF-1.4 tampered")
        assert (await get(BUYER, copy="original")).status_code == 410
        f.unlink()
        assert (await get(BUYER, copy="original")).status_code == 410


@pytest.mark.asyncio
async def test_a_bad_copy_value_is_refused(world):
    with patched(Renderer()):
        assert (await get(BUYER, copy="newest")).status_code == 400


@pytest.mark.asyncio
async def test_a_buyer_cannot_download_another_users_original(world):
    r = Renderer()
    with patched(r):
        await get(BUYER)
        stranger = await get(PRO, copy="original")  # entitled to render (premium), but the original is the buyer's
    assert stranger.status_code == 404 and (await renders("kind = 'original'"))[0]["user_id"] == "buyer"


# --- who else renders ----------------------------------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_a_subscriber_without_a_purchase_keeps_a_render_row_and_no_pdf(world):
    r = Renderer()
    with patched(r):
        resp = await get(PRO)
    assert resp.status_code == 200 and resp.headers["x-report-copy"] == "updated" and r.copy_of == [None]
    (row,) = await renders()
    assert row["purchase_id"] is None and row["user_id"] == "pro" and row["kind"] == "updated" and row["pdf_path"] is None
    assert not world["root"].exists()


@pytest.mark.asyncio
async def test_a_mock_render_is_never_recorded(world):
    with patched(Renderer()):
        resp = await get(BOSS, mock="true")
    assert resp.status_code == 200 and await renders() == [] and not world["root"].exists()


@pytest.mark.asyncio
async def test_a_bookkeeping_failure_never_costs_the_buyer_their_report(world):
    r = Renderer()
    with patched(r), patch.object(db, "record_render", new=AsyncMock(side_effect=RuntimeError("disk full"))):
        resp = await get(BUYER)
    assert resp.status_code == 200 and resp.content == b"%PDF-1.4 render-1"


# --- the original is stored once, by the database's own rule ----------------------------------------------------------------------

@pytest.mark.asyncio
async def test_a_second_original_is_refused_and_leaves_no_file(world):
    pid = await db.find_report_purchase("buyer", LAT, LON, pin=PIN)
    args = dict(user_id="buyer", purchase_id=pid, pin=PIN, lat=LAT, lon=LON, facts={"v": 1}, vintages=[], language="en")
    await db.record_render(kind="original", pdf=b"%PDF first", **args)
    before = sorted(p.name for p in (world["root"] / str(pid)).iterdir())
    with pytest.raises(db.OriginalExists):
        await db.record_render(kind="original", pdf=b"%PDF second", **args)
    assert sorted(p.name for p in (world["root"] / str(pid)).iterdir()) == before  # no stray file, no .tmp
    row = await db.get_original_render(pid)
    assert db.read_original_pdf(row) == b"%PDF first"


@pytest.mark.asyncio
async def test_a_race_for_the_original_makes_the_loser_an_updated_copy(world):
    r = Renderer()
    real = db.record_render
    calls = {"n": 0}

    async def raced(**kw):
        calls["n"] += 1
        if calls["n"] == 1:  # another request stored the original between the check and the insert
            await real(**{**kw, "pdf": b"%PDF the-winner"})
            raise db.OriginalExists("1")
        return await real(**kw)

    with patched(r), patch.object(db, "record_render", new=raced):
        resp = await get(BUYER)
    assert resp.status_code == 200 and resp.headers["x-report-copy"] == "updated"
    assert [x["kind"] for x in await renders()] == ["original", "updated"]


# --- Settings ---------------------------------------------------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_the_purchase_list_says_which_purchases_have_an_original(world):
    app.dependency_overrides[require_auth] = lambda: BUYER
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as ac:
            before = (await ac.get("/api/me/purchases")).json()["purchases"]
            assert before[0]["original"] is None  # bought before originals were kept: its next download becomes one
            with patched(Renderer()):
                await get(BUYER)
            app.dependency_overrides[require_auth] = lambda: BUYER
            after = (await ac.get("/api/me/purchases")).json()["purchases"]
    finally:
        app.dependency_overrides.pop(require_auth, None)
    assert after[0]["original"]["available"] is True and after[0]["original"]["rendered_at"] > 0


# --- the cover --------------------------------------------------------------------------------------------------------------------

def test_the_cover_of_an_updated_copy_says_when_the_first_one_was_made():
    page = render_report_html(make_report(), "en", report_date="October 22, 2026", copy_of="2026-10-02")
    cover = page[: page.index("TABLE OF CONTENTS")]
    assert 'data-testid="updated-copy"' in cover and "Updated copy of the report first generated on October 02, 2026" in cover  # the report's own date format
    assert "It reflects today&#39;s data" in cover
    plain = render_report_html(make_report(), "en", report_date="October 22, 2026")
    assert "updated-copy" not in plain[: plain.index("TABLE OF CONTENTS")]


# --- account deletion ----------------------------------------------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_deleting_an_account_removes_its_pdfs_and_render_rows_but_not_the_purchase_ledger(world):
    with patched(Renderer()):
        await get(BUYER)
        await get(BUYER)
        await get(PRO)
    (orig,) = await renders("kind = 'original'")
    path = world["root"] / orig["pdf_path"]
    assert path.is_file()
    out = await db.delete_user_account("buyer")
    assert out["report_files_deleted"] == 1 and not path.exists() and not path.parent.exists()
    left = await renders()
    assert [x["user_id"] for x in left] == ["pro"]  # the subscriber's row is untouched
    cur = await db._get_db().execute("SELECT user_id, status FROM report_purchases WHERE stripe_session_id = 'cs_test_1'")
    row = await cur.fetchone()
    assert row["user_id"] is None and row["status"] == "completed"  # tombstoned, as before
