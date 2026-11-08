"""Per-task wall-clock timing for one request (front-end rewrite Phase 2, decision Item 81).

A request opens a ``Collector`` with ``collect()``; anything awaited inside it, in any task created after that
(asyncio copies the context into new tasks, and the collector is one shared object), can record a span with
``timed(name, awaitable)`` or ``with span(name):``. Outside a collector both are pass-throughs, so the chat path
and the report path, which share these retrieval functions, pay one ContextVar lookup and record nothing.

Spans never change behavior: an exception is recorded as ``ok: False`` and re-raised unchanged.

Names are dotted by domain (``property.sales``, ``regulatory.flood``); a span recorded twice under one name
(a retried call) keeps every occurrence, and ``summary()`` reports the total and the count.
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any, TypeVar

T = TypeVar("T")


@dataclass
class Span:
    name: str
    start_ms: float  # since the collector opened
    ms: float
    ok: bool
    wait_ms: float | None = None  # time queued on the retrieval semaphore before the span started


@dataclass
class Collector:
    t0: float = field(default_factory=time.perf_counter)
    spans: list[Span] = field(default_factory=list)

    def now_ms(self) -> float:
        return (time.perf_counter() - self.t0) * 1000.0

    def summary(self) -> dict[str, dict[str, Any]]:
        """``{name: {ms, start_ms, end_ms, ok, n[, wait_ms]}}`` in start order; durations rounded to 0.1 ms."""
        out: dict[str, dict[str, Any]] = {}
        for s in sorted(self.spans, key=lambda s: s.start_ms):
            row = out.get(s.name)
            if row is None:
                row = out[s.name] = {"ms": 0.0, "start_ms": round(s.start_ms, 1), "end_ms": 0.0, "ok": True, "n": 0}
            row["ms"] = round(row["ms"] + s.ms, 1)
            row["end_ms"] = round(max(row["end_ms"], s.start_ms + s.ms), 1)
            row["ok"] = row["ok"] and s.ok
            row["n"] += 1
            if s.wait_ms is not None:
                row["wait_ms"] = round(row.get("wait_ms", 0.0) + s.wait_ms, 1)
        return out


_current: ContextVar[Collector | None] = ContextVar("urbanlayer_timing", default=None)


@contextmanager
def collect() -> Iterator[Collector]:
    """Open a collector for the code inside the block (and every task it starts)."""
    c = Collector()
    token = _current.set(c)
    try:
        yield c
    finally:
        _current.reset(token)


def current() -> Collector | None:
    return _current.get()


@contextmanager
def span(name: str, *, wait_ms: float | None = None) -> Iterator[None]:
    c = _current.get()
    if c is None:
        yield
        return
    start = c.now_ms()
    ok = False
    try:
        yield
        ok = True
    finally:
        c.spans.append(Span(name, start, c.now_ms() - start, ok, wait_ms))


async def timed(name: str, aw: Awaitable[T], *, wait_ms: float | None = None) -> T:
    """Await ``aw``, recording a span named ``name`` when a collector is open."""
    if _current.get() is None:
        return await aw
    with span(name, wait_ms=wait_ms):
        return await aw
