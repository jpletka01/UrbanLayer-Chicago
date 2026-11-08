"""One in-flight call per key, shared by every request that asks for it (decision Item 89).

The Profile's parts can ask the same source at the same moment: the first screen and the Overview both resolve
the address and look up the zoning point; two visitors open the same parcel; a Retry lands while the first try is
still running. ``shared(key, factory)`` runs ``factory()`` once per key while it is in flight and gives every
caller its result (or its exception). The TTL caches behind each source still decide what is kept afterwards,
so nothing here caches: a key leaves the map the moment its call finishes.

Cancellation is reference-counted. A caller that goes away (a visitor left the page) stops waiting; the call
itself is cancelled only when no caller is waiting for it any more. The exception is a late source past its
deadline (``shared_with_deadline``): the caller stops waiting but the call is kept to its end, so the source's
cache fills and the visitor's Retry is usually instant (or joins the same call).

One process: production runs a single uvicorn worker, so a module-level map sees every request.
"""

from __future__ import annotations

import asyncio
import contextvars
from collections.abc import Awaitable, Callable, Hashable
from dataclasses import dataclass
from typing import Any


@dataclass
class _Entry:
    task: asyncio.Task
    waiters: int = 0
    keep: bool = False
    joined: int = 0  # callers that found the call already running (tests, logs)


_inflight: dict[Hashable, _Entry] = {}


def in_flight() -> int:
    """How many keys are running now (tests)."""
    return len(_inflight)


def _start(key: Hashable, factory: Callable[[], Awaitable[Any]], keep: bool) -> _Entry:
    async def run() -> Any:
        return await factory()

    # A fresh context copy: the call outlives the first caller's request when another caller (or keep) needs it.
    task = asyncio.get_running_loop().create_task(run(), context=contextvars.copy_context())
    entry = _Entry(task=task, keep=keep)
    _inflight[key] = entry

    def _forget(_t: asyncio.Task) -> None:
        if _inflight.get(key) is entry:
            del _inflight[key]
        if not _t.cancelled():
            _t.exception()  # retrieve it, so a call nobody awaited any more never logs "never retrieved"

    task.add_done_callback(_forget)
    return entry


async def shared(key: Hashable, factory: Callable[[], Awaitable[Any]], *, keep: bool = False) -> Any:
    """Await the one call for ``key``, starting it with ``factory()`` when none is running."""
    entry = _inflight.get(key)
    if entry is None:
        entry = _start(key, factory, keep)
    else:
        entry.joined += 1
        entry.keep = entry.keep or keep
    entry.waiters += 1
    try:
        return await asyncio.shield(entry.task)
    finally:
        entry.waiters -= 1
        if entry.waiters == 0 and not entry.task.done() and not entry.keep:
            entry.task.cancel()


async def shared_with_deadline(
    key: Hashable, factory: Callable[[], Awaitable[Any]], deadline_s: float,
) -> tuple[bool, Any]:
    """``(True, result)`` when the call for ``key`` finishes within ``deadline_s``; ``(False, None)`` when it
    doesn't. Past the deadline the caller stops waiting and the call keeps running to its own end (``keep``).
    An exception from the call is raised as from ``shared``."""
    entry = _inflight.get(key)
    if entry is None:
        entry = _start(key, factory, keep=False)
    else:
        entry.joined += 1
    entry.waiters += 1
    try:
        done, _ = await asyncio.wait({entry.task}, timeout=deadline_s)
        if not done:
            # Past the deadline: stop waiting, let the fetch finish so its cache fills for the Retry.
            entry.keep = True
            return False, None
        return True, entry.task.result()
    finally:
        # A caller that left before the deadline (the visitor closed the page) cancels the call once nobody
        # else waits for it.
        entry.waiters -= 1
        if entry.waiters == 0 and not entry.task.done() and not entry.keep:
            entry.task.cancel()


def _reset_for_tests() -> None:
    for entry in list(_inflight.values()):
        entry.task.cancel()
    _inflight.clear()
