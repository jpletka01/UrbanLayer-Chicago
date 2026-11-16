"""Deep analysis (decision Item 124): who may read it, what it never does, and the builder's saved project."""

from __future__ import annotations

import json
import math
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient

from backend import db, deep_analysis, entitlements
from backend.auth import get_current_user, require_auth
from backend.main import ResolvedLocation, app
from backend.models import ContextObject, PropertySummary, RegulatorySummary, ReportData, ZoningStandards
from backend.rate_limit import clear_rate_limits
from backend.report_builder import envelope_geometry

LOT_A = "14331030110000"
UNIT_A = "14331030111002"  # a condo unit on lot A
LOT_B = "14283190070000"
FT_LAT = 364_000.0  # feet per degree of latitude, near enough for a test outline


def _rect(lon: float, lat: float, width_ft: float, depth_ft: float) -> dict:
    """A width x depth lot, its short sides facing north and south."""
    dlon = width_ft / (FT_LAT * math.cos(math.radians(lat)))
    dlat = depth_ft / FT_LAT
    ring = [[lon, lat], [lon + dlon, lat], [lon + dlon, lat + dlat], [lon, lat + dlat], [lon, lat]]
    return {"type": "Polygon", "coordinates": [ring]}


def _report(outline: dict | None = None, **reg) -> ReportData:
    prop = PropertySummary(land_sqft=3125, bldg_sqft=2400, parcel_geometry=outline or _rect(-87.6447, 41.9237, 25, 125))
    ctx = ContextObject(property=prop, regulatory=RegulatorySummary(**reg))
    std = ZoningStandards(zone_class="RT-4", far=1.2, front_setback_ft=15, side_setback_ft=2, rear_setback_ft=30,
                          extraction_confidence="definitions")
    return ReportData(address="642 W Belden Ave", lat=41.9237, lon=-87.6447, context=ctx, zoning_standards=std,
                      resolved_pin=LOT_A, resolved_confidence="authoritative")


@pytest_asyncio.fixture
async def store(tmp_path):
    settings = MagicMock()
    settings.db_path = str(tmp_path / "test.db")
    settings.upload_dir = tmp_path / "uploads"
    settings.report_store_dir = tmp_path / "reports"
    with patch("backend.db.get_settings", return_value=settings):
        await db.init_db()
        clear_rate_limits()
        deep_analysis.clear_state()
        yield
        await db.close_db()


@pytest.fixture(autouse=True)
def _no_address_lookup():
    with patch("backend.retrieval.property.address_points.pin_to_address", AsyncMock(return_value="642 W BELDEN AVE")):
        yield


@pytest.fixture
def fetch():
    """The report's data path, mocked; counts calls. A model client reached anywhere fails the test."""
    calls: list[dict] = []

    async def fake_fetch(lat, lon, address, **kw):
        calls.append(kw)
        return _report(), None, None

    def no_model(*a, **k):
        raise AssertionError("Deep analysis reached a model client")

    with patch("backend.main._resolve_location", AsyncMock(return_value=ResolvedLocation(
            41.9237, -87.6447, "642 W Belden Ave", LOT_A, "authoritative", "pin"))), \
         patch("backend.report_builder._fetch_report_data", side_effect=fake_fetch), \
         patch("backend.llm.tracked_create", side_effect=no_model), \
         patch("backend.llm.tracked_stream", side_effect=no_model):
        yield calls


@pytest.fixture
def as_user():
    """Sign-in on (so CSRF applies); the user is whatever the test says."""
    auth_settings = MagicMock()
    auth_settings.google_client_id = "test-client"
    auth_settings.microsoft_client_id = ""
    auth_settings.apple_client_id = ""
    auth_settings.auth_dev_login = False
    auth_settings.jwt_secret = "test-secret"

    def _set(user: dict | None) -> TestClient:
        app.dependency_overrides[get_current_user] = lambda: user
        if user is None:
            def _deny():
                from fastapi import HTTPException
                raise HTTPException(status_code=401, detail="Authentication required")
            app.dependency_overrides[require_auth] = _deny
        else:
            app.dependency_overrides[require_auth] = lambda: user
        client = TestClient(app)
        client.cookies.set("csrf_token", "t")
        client.headers["x-csrf-token"] = "t"
        return client

    with patch("backend.auth.get_settings", return_value=auth_settings), \
         patch("backend.auth._jwt_secret", return_value="test-secret"):
        yield _set
    app.dependency_overrides.clear()


async def _user(uid: str, tier: str = "free") -> dict:
    user, _ = await db.sign_in_identity({"provider": "google", "subject": f"s-{uid}"}, uid)
    return {**user, "tier": tier}


class TestGate:
    @pytest.mark.asyncio
    async def test_signed_out_is_401(self, store, as_user, fetch):
        assert as_user(None).get(f"/api/deep-analysis?pin={LOT_A}").status_code == 401

    @pytest.mark.asyncio
    async def test_free_unused_is_locked_and_reading_claims_nothing(self, store, as_user, fetch):
        user = await _user("u1")
        r = as_user(user).get(f"/api/deep-analysis?pin={LOT_A}")
        assert r.status_code == 403 and r.json()["detail"] == {"error": "deep_analysis_locked"}
        assert "lot" not in r.text and not fetch
        assert (await entitlements.status(user))["deep_analysis"]["free_left"] == 1

    @pytest.mark.asyncio
    async def test_free_lot_opens_and_another_stays_locked(self, store, as_user, fetch):
        user = await _user("u1")
        await entitlements.claim(user, LOT_A)
        c = as_user(user)
        r = c.get(f"/api/deep-analysis?pin={LOT_A}")
        assert r.status_code == 200 and r.json()["pin"] == LOT_A
        assert c.get(f"/api/deep-analysis?pin={LOT_B}").status_code == 403

    @pytest.mark.asyncio
    async def test_a_condo_unit_opens_its_lot(self, store, as_user, fetch):
        user = await _user("u1")
        await entitlements.claim(user, LOT_A)
        assert as_user(user).get(f"/api/deep-analysis?pin={UNIT_A}").status_code == 200
        # and claiming through the unit is the same lot, not a second one
        assert (await entitlements.claim(user, UNIT_A))["pin"] == LOT_A

    @pytest.mark.asyncio
    async def test_pro_and_admin_open_any_lot_without_claiming(self, store, as_user, fetch):
        for tier in ("premium", "admin"):
            user = await _user(f"u-{tier}", tier)
            assert as_user(user).get(f"/api/deep-analysis?pin={LOT_B}").status_code == 200
            assert (await entitlements.free_pin(user["id"])) is None

    @pytest.mark.asyncio
    async def test_pro_lapses_to_the_free_lot_only(self, store, as_user, fetch):
        user = await _user("u1", "premium")
        await entitlements.claim({**user, "tier": "free"}, LOT_A)
        lapsed = {**user, "tier": "free"}
        c = as_user(lapsed)
        assert c.get(f"/api/deep-analysis?pin={LOT_A}").status_code == 200
        assert c.get(f"/api/deep-analysis?pin={LOT_B}").status_code == 403

    @pytest.mark.asyncio
    async def test_bad_pin_is_422(self, store, as_user, fetch):
        user = await _user("u1", "premium")
        assert as_user(user).get("/api/deep-analysis?pin=1433").status_code == 422


class TestNoModelNoRasters:
    @pytest.mark.asyncio
    async def test_fetch_runs_without_rasters_and_no_model(self, store, as_user, fetch):
        user = await _user("u1", "premium")
        assert as_user(user).get(f"/api/deep-analysis?pin={LOT_A}&language=es").status_code == 200
        assert fetch == [{"pin": LOT_A, "confidence": "authoritative", "language": "es", "rasters": False}]

    @pytest.mark.asyncio
    async def test_a_second_read_is_cached(self, store, as_user, fetch):
        user = await _user("u1", "premium")
        c = as_user(user)
        c.get(f"/api/deep-analysis?pin={LOT_A}")
        c.get(f"/api/deep-analysis?pin={LOT_A}")
        assert len(fetch) == 1


class TestPartialCache:
    @pytest.mark.asyncio
    async def test_a_failed_source_is_kept_briefly_and_still_named(self, store, as_user):
        calls = []

        async def fetch_with_gap(lat, lon, address, **kw):
            calls.append(kw)
            r = _report()
            r.partial_failures = ["EPA brownfield sites"]
            return r, None, None

        user = await _user("u1", "premium")
        with patch("backend.main._resolve_location", AsyncMock(return_value=ResolvedLocation(
                41.9237, -87.6447, "642 W Belden Ave", LOT_A, "authoritative", "pin"))), \
             patch("backend.report_builder._fetch_report_data", side_effect=fetch_with_gap):
            c = as_user(user)
            first = c.get(f"/api/deep-analysis?pin={LOT_A}").json()
            second = c.get(f"/api/deep-analysis?pin={LOT_A}").json()
        assert len(calls) == 1
        assert first["partial_failures"] == second["partial_failures"] == ["EPA brownfield sites"]
        assert deep_analysis._cache.get((LOT_A, "en")) is None  # not in the 30-minute cache


class TestAntiScrape:
    @pytest.mark.asyncio
    async def test_sixty_first_lot_in_a_day_is_429_and_a_repeat_is_free(self, store, as_user, fetch):
        user = await _user("u1", "premium")
        for i in range(deep_analysis.LOTS_PER_DAY):
            deep_analysis._count_lot(user["id"], f"14{i:08d}0000")
        deep_analysis._count_lot(user["id"], "14000000050000")  # opened today already
        deep_analysis._count_lot(user["id"], "14000000051234")  # a unit of the same lot
        r = as_user(user).get(f"/api/deep-analysis?pin={LOT_B}")
        assert r.status_code == 429 and r.json()["detail"] == {"error": "deep_analysis_daily_lots"}

    @pytest.mark.asyncio
    async def test_eleventh_request_in_a_minute_is_429(self, store, as_user, fetch):
        user = await _user("u1", "premium")
        c = as_user(user)
        codes = [c.get(f"/api/deep-analysis?pin={LOT_A}").status_code for _ in range(11)]
        assert codes[:10] == [200] * 10 and codes[10] == 429


PROJECT = {"kind": "three_flat", "units": 3, "stories": 3, "floor_area_sqft": 3750}
NUMBERS = {"rent_unit_month": 2100, "land_price": 450000, "build_cost_sqft": 300, "profit_on_cost": 0.2, "target_yield": 0.075}


class TestProject:
    @pytest.mark.asyncio
    async def test_round_trip_and_units_share_the_lot(self, store, as_user):
        user = await _user("u1", "premium")
        c = as_user(user)
        assert c.get(f"/api/deep-analysis/project?pin={LOT_A}").json()["project"] is None
        r = c.put("/api/deep-analysis/project", json={"pin": LOT_A, "project": PROJECT, "numbers": NUMBERS, "step": 2})
        assert r.status_code == 200
        got = c.get(f"/api/deep-analysis/project?pin={UNIT_A}").json()
        assert got["project"] == PROJECT and got["step"] == 2 and got["numbers"]["rent_unit_month"] == 2100 and got["numbers"]["mode"] == "sell"

    @pytest.mark.asyncio
    async def test_own_projects_focus_and_card_prices_round_trip(self, store, as_user):
        user = await _user("u1", "premium")
        c = as_user(user)
        empty = c.get(f"/api/deep-analysis/project?pin={LOT_A}").json()
        assert empty["own"] == [] and empty["focus"] is None and empty["prices"] == {}
        own = [{"id": "a1", "units": 4, "stories": 3, "floor_area_sqft": 4500},
               {"id": "b2", "units": 6, "stories": 4, "floor_area_sqft": 6000}]
        body = {"pin": LOT_A, "project": {**PROJECT, "kind": "own", "units": 6}, "own": own, "focus": "own:b2",
                "prices": {"own:b2": {"sale_price_unit": 410000}, "three_flat": {"rent_unit_month": 3900}}}
        assert c.put("/api/deep-analysis/project", json=body).status_code == 200
        got = c.get(f"/api/deep-analysis/project?pin={UNIT_A}").json()
        assert got["own"] == own and got["focus"] == "own:b2" and got["project"]["units"] == 6
        assert got["prices"] == {"own:b2": {"sale_price_unit": 410000}, "three_flat": {"rent_unit_month": 3900}}

    @pytest.mark.asyncio
    async def test_a_row_saved_before_the_own_list_still_reads(self, store, as_user):
        user = await _user("u1", "premium")
        c = as_user(user)
        c.get(f"/api/deep-analysis/project?pin={LOT_A}")
        await db._get_db().execute(
            "INSERT INTO deep_projects (user_id, pin, project_json, numbers_json, step, updated_at) VALUES (?, ?, ?, ?, 0, 0)",
            ("u1", LOT_A[:10], json.dumps(PROJECT), json.dumps({"mode": "sell"})))
        await db._get_db().commit()
        got = c.get(f"/api/deep-analysis/project?pin={LOT_A}").json()
        assert got["project"] == PROJECT and got["own"] == [] and got["focus"] is None and got["prices"] == {}

    @pytest.mark.asyncio
    @pytest.mark.parametrize("body", [
        {"pin": LOT_A, "project": {**PROJECT, "units": -1}},
        {"pin": LOT_A, "project": {**PROJECT, "kind": "skyscraper"}},
        {"pin": LOT_A, "project": PROJECT, "user_id": "u2"},
        {"pin": LOT_A, "numbers": {**NUMBERS, "target_yield": 5}},
        {"pin": LOT_A, "mode": "flip"},
        {"pin": LOT_A, "step": 99},
        {"pin": "1433"},
        {"pin": LOT_A, "own": [{"id": f"p{i}", "units": 3, "stories": 3, "floor_area_sqft": 3000} for i in range(7)]},
        {"pin": LOT_A, "own": [{"id": "Bad Id!", "units": 3, "stories": 3, "floor_area_sqft": 3000}]},
        {"pin": LOT_A, "focus": "skyscraper"},
        {"pin": LOT_A, "prices": {"own:x": {"sale_price_unit": -5}}},
        {"pin": LOT_A, "prices": {"<script>": {"sale_price_unit": 5}}},
    ])
    async def test_tampered_bodies_are_422(self, store, as_user, body):
        user = await _user("u1", "premium")
        assert as_user(user).put("/api/deep-analysis/project", json=body).status_code == 422

    @pytest.mark.asyncio
    async def test_locked_lot_is_403(self, store, as_user):
        user = await _user("u1")
        c = as_user(user)
        assert c.get(f"/api/deep-analysis/project?pin={LOT_A}").status_code == 403
        assert c.put("/api/deep-analysis/project", json={"pin": LOT_A, "project": PROJECT}).status_code == 403

    @pytest.mark.asyncio
    async def test_another_account_never_sees_it(self, store, as_user):
        a = await _user("a", "premium")
        b = await _user("b", "premium")
        as_user(a).put("/api/deep-analysis/project", json={"pin": LOT_A, "project": PROJECT})
        assert as_user(b).get(f"/api/deep-analysis/project?pin={LOT_A}").json()["project"] is None

    @pytest.mark.asyncio
    async def test_put_without_csrf_is_403(self, store, as_user):
        user = await _user("u1", "premium")
        c = as_user(user)
        del c.headers["x-csrf-token"]
        assert c.put("/api/deep-analysis/project", json={"pin": LOT_A, "project": PROJECT}).status_code == 403

    @pytest.mark.asyncio
    async def test_deleting_the_account_drops_projects_but_keeps_the_free_use(self, store, as_user):
        user = await _user("u1")
        await entitlements.claim(user, LOT_A)
        as_user(user).put("/api/deep-analysis/project", json={"pin": LOT_A, "project": PROJECT})
        await db.delete_user_account("u1")
        cur = await db._get_db().execute("SELECT COUNT(*) FROM deep_projects")
        assert (await cur.fetchone())[0] == 0
        again = await _user("u2")  # different subject: not the same person
        assert (await entitlements.free_pin(again["id"])) is None


class TestPayload:
    def test_sections_and_checklist(self):
        p = deep_analysis.build_payload(_report(in_special_flood_hazard=True), pin=LOT_A)
        assert p["lot"]["land_sqft"] == 3125 and p["zoning"]["standards"]["far"] == 1.2
        assert p["envelope"] and p["envelope"]["approximate"] is False
        keys = {i["key"]: i for i in p["checklist"]}
        assert keys["flood_sfha"]["state"] == "warn" and keys["title"]["state"] == "todo"
        assert "flood" not in keys

    def test_no_outline_means_no_envelope(self):
        r = _report()
        r.context.property.parcel_geometry = None
        assert deep_analysis.build_payload(r, pin=LOT_A)["envelope"] is None


class TestEnvelope:
    STD = ZoningStandards(zone_class="RT-4", front_setback_ft=15, side_setback_ft=2, rear_setback_ft=30,
                          extraction_confidence="definitions")

    def test_plain_lot_insets_by_role(self):
        # 642 W Belden: an east-west street, even number = north side, so the front is the lot's south edge.
        env = envelope_geometry(_rect(-87.6447, 41.9237, 25, 125), self.STD, "642 W Belden Ave")
        roles = sorted(e["role"] for e in env["edges"])
        assert roles == ["front", "rear", "side", "side"] and env["approximate"] is False
        assert env["method"] == "address_grid"
        front = next(e for e in env["edges"] if e["role"] == "front")
        assert front["from"][1] == front["to"][1] == 41.9237  # the southern edge
        # 25 x 125 minus 2 + 2 ft sides and 15 + 30 ft front/rear = 21 x 80
        assert abs(env["footprint_sqft"] - 21 * 80) < 25

    def test_odd_number_fronts_north(self):
        env = envelope_geometry(_rect(-87.6447, 41.9237, 25, 125), self.STD, "643 W Belden Ave")
        front = next(e for e in env["edges"] if e["role"] == "front")
        assert front["from"][1] > 41.9237 and env["approximate"] is False

    def test_split_sides_are_merged(self):
        # PTAXSIM puts a vertex every few metres along a side; the footprint must still inset.
        ring = _rect(-87.6447, 41.9237, 25, 125)["coordinates"][0]
        (x0, y0), (_x1, y1) = ring[1], ring[2]
        split = ring[:2] + [[x0, y0 + (y1 - y0) * f] for f in (0.25, 0.5, 0.75)] + ring[2:]
        env = envelope_geometry({"type": "Polygon", "coordinates": [split]}, self.STD, "642 W Belden Ave")
        assert len(env["edges"]) == 4 and env["footprint"] and env["approximate"] is False

    def test_no_address_answer_is_approximate(self):
        for addr in (None, "", "Milwaukee Ave"):  # no address, or none we can read a grid side from
            env = envelope_geometry(_rect(-87.6447, 41.9237, 25, 125), self.STD, addr)
            assert env["approximate"] is True and env["method"] == "shorter_width_edge"

    def test_odd_lot_is_approximate(self):
        lon, lat = -87.6447, 41.9237
        d = 1 / FT_LAT
        k = 1 / (FT_LAT * math.cos(math.radians(lat)))
        # an L-shaped lot: six main edges
        ring = [[lon, lat], [lon + 50 * k, lat], [lon + 50 * k, lat + 40 * d], [lon + 25 * k, lat + 40 * d],
                [lon + 25 * k, lat + 125 * d], [lon, lat + 125 * d], [lon, lat]]
        env = envelope_geometry({"type": "Polygon", "coordinates": [ring]}, self.STD)
        assert env["approximate"] is True

    def test_missing_outline_is_none_never_a_rectangle(self):
        assert envelope_geometry({}, self.STD) is None
        assert envelope_geometry({"type": "Polygon", "coordinates": []}, self.STD) is None


class TestMigration:
    @pytest.mark.asyncio
    async def test_v20_database_gains_deep_projects(self, tmp_path):
        import aiosqlite
        settings = MagicMock()
        settings.db_path = str(tmp_path / "old.db")
        with patch("backend.db.get_settings", return_value=settings):
            await db.init_db()
            await db._get_db().execute("DROP TABLE deep_projects")
            await db._get_db().execute("UPDATE schema_version SET version = 20")
            await db._get_db().commit()
            await db.close_db()
            await db.init_db()
            cur = await db._get_db().execute("SELECT version FROM schema_version")
            assert (await cur.fetchone())[0] == 21
            cur = await db._get_db().execute("SELECT name FROM sqlite_master WHERE name = 'deep_projects'")
            assert await cur.fetchone()
            await db.close_db()
        assert aiosqlite


class TestInputs:
    def test_last_sale_skips_nominal_transfers_and_assumptions_carry_sources(self):
        from backend.models import SaleRecord
        r = _report()
        r.context.property.sales_history = [
            SaleRecord(date="2023-05-01", price=1_207_000, deed_type="WARRANTY"),
            SaleRecord(date="2024-02-01", price=1, deed_type="QUIT CLAIM"),
            SaleRecord(date="2019-01-01", price=900_000),
        ]
        inp = deep_analysis.build_payload(r, pin=LOT_A)["inputs"]
        assert inp["last_sale"] == {"price": 1_207_000, "date": "2023-05-01", "deed_type": "WARRANTY"}
        for a in inp["assumptions"].values():
            assert a["low"] <= a["value"] <= a["high"] and a["source"] and a["as_of"]
        assert inp["lot"]["land_sqft"] == 3125 and inp["lot"]["far"] == 1.2

    def test_no_sales_no_rent_is_none_not_zero(self):
        inp = deep_analysis.build_payload(_report(), pin=LOT_A)["inputs"]
        assert inp["last_sale"] is None and inp["area_sales"] == {} and inp["rents"]["census"] == {}

    def test_new_construction_price_comes_from_the_committed_artifact(self):
        r = _report()
        r.context.community_area = 7  # Lincoln Park: enough condo sales of its own
        nc = deep_analysis.build_payload(r, pin=LOT_A)["inputs"]["new_construction"]
        assert nc["low"] <= nc["value"] <= nc["high"] and abs(nc["value"] - nc["level"] * nc["premium"]) <= 1
        assert nc["pooled_areas"] is None and nc["n"] >= 30 and nc["premium_n"] > 0 and len(nc["years"]) == 2

    def test_a_thin_area_borrows_its_neighbors_and_says_so(self):
        from backend.deep_inputs import load_new_construction
        thin = next(ca for ca, row in load_new_construction()["community_areas"].items() if row["areas"])
        r = _report()
        r.context.community_area = int(thin)
        nc = deep_analysis.build_payload(r, pin=LOT_A)["inputs"]["new_construction"]
        assert nc["pooled_areas"] and len(nc["pooled_areas"]) >= 2 and nc["n"] >= 30

    def test_no_community_area_is_none_and_a_missing_artifact_is_unchecked(self, monkeypatch):
        from backend import deep_inputs
        r = _report()
        r.context.community_area = None
        inp = deep_analysis.build_payload(r, pin=LOT_A)["inputs"]
        assert inp["new_construction"] is None and inp["unchecked"] == []

        def boom():
            raise deep_inputs.NewConstructionArtifactError("gone")
        monkeypatch.setattr(deep_inputs, "load_new_construction", boom)
        r.context.community_area = 7
        inp = deep_analysis.build_payload(r, pin=LOT_A)["inputs"]
        assert inp["new_construction"] is None and inp["unchecked"] == ["new_construction"]


def test_new_construction_builder_pools_to_min_n_and_bands_by_the_premium():
    from ingestion.build_new_construction_artifact import MIN_N, build
    res = {
        "years": [2023, 2025], "max_age": 2,
        "community_areas": {"1": {"condo_any_age": {"per_sqft": {"n": 40, "median": 300}}},
                            "2": {"condo_any_age": {"per_sqft": {"n": 5, "median": 200}}}},
        "records": [["1", "condo", 2024, v] for v in (300, 330, 360, 420)],
    }
    art, meta = build(res)
    a1, a2 = art["community_areas"]["1"], art["community_areas"]["2"]
    assert art["premium"]["n"] == 4 and a1["areas"] is None and a1["new_sales"] == 4
    assert a1["low"] <= a1["value"] <= a1["high"]
    assert a2["areas"][0] == "2" and "1" in a2["areas"] and a2["n"] >= MIN_N and a2["new_sales"] == 0
    assert meta["with_new_sales"] == 1
