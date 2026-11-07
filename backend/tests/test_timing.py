"""The per-task timing collector (decision Item 81): spans cross task boundaries, never change behavior,
and record nothing outside a collector."""

import asyncio

import pytest

from backend import timing


async def _sleep_ok(ms: float, value):
    await asyncio.sleep(ms / 1000)
    return value


async def _boom():
    await asyncio.sleep(0)
    raise ValueError("source down")


async def test_outside_a_collector_timed_is_a_pass_through():
    assert timing.current() is None
    assert await timing.timed("x", _sleep_ok(0, 7)) == 7
    with timing.span("y"):
        pass
    assert timing.current() is None


async def test_spans_from_child_tasks_land_in_the_request_collector():
    with timing.collect() as c:
        task = asyncio.create_task(timing.timed("child.task", _sleep_ok(20, "a")))
        got = await asyncio.gather(task, timing.timed("gathered", _sleep_ok(5, "b")))
        with timing.span("sync"):
            pass
    assert got == ["a", "b"]
    s = c.summary()
    assert set(s) == {"child.task", "gathered", "sync"}
    assert s["child.task"]["ms"] >= 15
    assert all(row["ok"] and row["n"] == 1 for row in s.values())
    assert timing.current() is None  # the collector closes with the block


async def test_a_failure_is_recorded_and_re_raised_unchanged():
    with timing.collect() as c:
        with pytest.raises(ValueError, match="source down"):
            await timing.timed("bad", _boom())
        done = await asyncio.gather(timing.timed("bad2", _boom()), return_exceptions=True)
    assert isinstance(done[0], ValueError)
    s = c.summary()
    assert s["bad"]["ok"] is False and s["bad2"]["ok"] is False


async def test_a_repeated_name_sums_and_counts_and_keeps_queue_wait():
    with timing.collect() as c:
        await timing.timed("retry", _sleep_ok(1, None), wait_ms=2.0)
        await timing.timed("retry", _sleep_ok(1, None), wait_ms=3.0)
    row = c.summary()["retry"]
    assert row["n"] == 2
    assert row["wait_ms"] == 5.0
    assert row["end_ms"] >= row["start_ms"] + row["ms"] - 0.2


async def test_scorecard_payload_carries_timings_only_behind_the_dev_switch(monkeypatch):
    from backend import main
    from backend.config import get_settings

    async def fake_payload(address, lat, lon, pin):
        await timing.timed("zoning", _sleep_ok(1, None))
        return {"address": address}

    monkeypatch.setattr(main, "_scorecard_payload", fake_payload)
    settings = get_settings()

    monkeypatch.setattr(settings, "profile_timings", False)
    assert "_timings" not in await main.scorecard(address="1 N State St")

    monkeypatch.setattr(settings, "profile_timings", True)
    monkeypatch.setattr(settings, "environment", "development")
    out = await main.scorecard(address="1 N State St")
    assert set(out["_timings"]["spans"]) == {"zoning"}
    assert out["_timings"]["total_ms"] > 0

    monkeypatch.setattr(settings, "environment", "production")
    assert "_timings" not in await main.scorecard(address="1 N State St")
