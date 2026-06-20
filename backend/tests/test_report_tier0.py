"""Tier-0 reliability regression tests.

Locks in the two render-reliability fixes from the Tier-0 investigation
(`claude-context/guides/report-v6-execution-plan.md` → "Tier-0"):

1. `_REPORT_SEM` bounds the number of concurrent report renders so concurrent
   reports can't OOM the single prod worker (the validated root cause).
2. A report still completes end-to-end when the upstream data is degraded
   (e.g. Cook County GIS down → no parcel geometry) — no crash path.

These run the real `/api/report` endpoint through an ASGI transport with the
heavy internals (data fetch, Jinja render, WeasyPrint) faked so the test
exercises the concurrency/offload wiring, not live APIs.
"""

import asyncio
from contextlib import ExitStack
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

import backend.main as main_mod
from backend.main import app, require_auth


def _premium_user():
    return {"id": "u1", "tier": "premium", "email": "t@example.com"}


class _FakeTemplate:
    def render(self, **kwargs):
        return "<html><body>report</body></html>"


class _FakeEnv:
    """Stand-in for jinja2.Environment so we skip rendering the real template
    (which needs a fully-populated ReportData)."""

    def __init__(self, *args, **kwargs):
        self.filters = {}
        self.globals = {}

    def get_template(self, name):
        return _FakeTemplate()


def _install_common_patches(stack: ExitStack, fetch_impl) -> None:
    """Patch the heavy/IO internals of report() so only the concurrency/offload
    wiring is exercised. `fetch_impl` is the async _fetch_report_data stand-in.

    The PDF render now runs in an isolated child process (backend/report_render.py);
    we patch the async `render_pdf` seam to return fake PDF bytes instantly rather
    than spawn a real WeasyPrint subprocess (which isn't installed in this env)."""
    app.dependency_overrides[require_auth] = _premium_user
    stack.callback(app.dependency_overrides.pop, require_auth, None)

    stack.enter_context(
        patch.object(
            main_mod, "_resolve_location",
            new=AsyncMock(return_value=main_mod.ResolvedLocation(
                41.93, -87.64, "Test Address", None, "approximate")),
        )
    )
    stack.enter_context(
        patch.object(main_mod, "_fetch_report_data", new=fetch_impl)
    )
    stack.enter_context(patch("jinja2.Environment", new=_FakeEnv))
    stack.enter_context(
        patch("backend.report_render.render_pdf",
              new=AsyncMock(return_value=b"%PDF-1.4 fake-tier0")),
    )


async def _fire(n: int) -> list[httpx.Response]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        return await asyncio.gather(
            *[ac.get("/api/report", params={"lat": 41.93, "lon": -87.64}) for _ in range(n)]
        )


def _tracking_fetch(tracker: dict, delay: float = 0.05):
    """Build a _fetch_report_data stand-in that records peak concurrency."""

    async def _fetch(lat, lon, addr, *, pin=None, confidence=None, language="en"):
        tracker["current"] += 1
        tracker["max"] = max(tracker["max"], tracker["current"])
        try:
            await asyncio.sleep(delay)
            return (MagicMock(), None, None)
        finally:
            tracker["current"] -= 1

    return _fetch


@pytest.mark.asyncio
async def test_report_serializes_under_semaphore_of_one():
    """With _REPORT_SEM = Semaphore(1), 3 concurrent reports run one at a time."""
    tracker = {"current": 0, "max": 0}
    with ExitStack() as stack:
        _install_common_patches(stack, _tracking_fetch(tracker))
        stack.enter_context(patch.object(main_mod, "_REPORT_SEM", asyncio.Semaphore(1)))
        results = await _fire(3)

    assert all(r.status_code == 200 for r in results)
    assert all(r.content.startswith(b"%PDF") for r in results)
    assert tracker["max"] == 1, f"semaphore(1) should serialize, saw {tracker['max']} in flight"


@pytest.mark.asyncio
async def test_report_concurrency_bounded_by_semaphore_value():
    """The peak in-flight renders never exceed the semaphore's value."""
    tracker = {"current": 0, "max": 0}
    with ExitStack() as stack:
        _install_common_patches(stack, _tracking_fetch(tracker))
        stack.enter_context(patch.object(main_mod, "_REPORT_SEM", asyncio.Semaphore(2)))
        results = await _fire(4)

    assert all(r.status_code == 200 for r in results)
    assert tracker["max"] <= 2, f"semaphore(2) breached: saw {tracker['max']} in flight"


@pytest.mark.asyncio
async def test_harness_can_observe_true_concurrency():
    """Sanity check: with a wide semaphore the harness genuinely runs requests
    concurrently — so the ==1 assertion above is the semaphore working, not the
    test harness accidentally serializing."""
    tracker = {"current": 0, "max": 0}
    with ExitStack() as stack:
        _install_common_patches(stack, _tracking_fetch(tracker))
        stack.enter_context(patch.object(main_mod, "_REPORT_SEM", asyncio.Semaphore(10)))
        results = await _fire(3)

    assert all(r.status_code == 200 for r in results)
    assert tracker["max"] == 3, "harness should run all 3 concurrently under a wide semaphore"


@pytest.mark.asyncio
async def test_report_completes_when_data_degraded():
    """Tier-0 degradation: when upstream data is degraded (GIS down → no parcel
    geometry, property=None), the report still renders end-to-end (200 + PDF)
    rather than crashing the worker."""

    async def _degraded_fetch(lat, lon, addr, *, pin=None, confidence=None, language="en"):
        # Simulates the validated degraded path: no geometry, no basemaps.
        report_data = MagicMock()
        report_data.context.parcel_zoning = None
        return (report_data, None, None)

    with ExitStack() as stack:
        _install_common_patches(stack, _degraded_fetch)
        results = await _fire(1)

    assert results[0].status_code == 200
    assert results[0].content.startswith(b"%PDF")
