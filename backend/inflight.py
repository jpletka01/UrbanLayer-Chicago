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
    joined: int = 0
    started: asyncio.Event | None = None  # shared_with_deadline: set when the call leaves its queue  # callers that found the call already running (tests, logs)


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
    key: Hashable,
    factory: Callable[[Callable[[], None]], Awaitable[Any]],
    deadline_s: float,
    *,
    queue_cap_s: float = 120.0,
) -> tuple[bool, Any]:
    """``(True, result)`` when the call for ``key`` finishes within ``deadline_s`` of starting; ``(False, None)``
    when it doesn't. ``factory(mark_started)`` must call ``mark_started()`` once the call actually begins (after
    any queue of its own), so time spent waiting for a slot doesn't count against the source (Item 89: the 20 s
    is the source's own time). Past the deadline the caller stops waiting and the call keeps running to its own
    end. An exception from the call is raised as from ``shared``."""
    entry = _inflight.get(key)
    if entry is None:
        started = asyncio.Event()
        entry = _start(key, lambda: factory(started.set), keep=False)
        entry.started = started
    else:
        entry.joined += 1
    started = entry.started
    entry.waiters += 1
    try:
        if started is not None and not started.is_set():
            # Queued behind other late sources: wait for the slot (bounded), then start the deadline.
            waiter = asyncio.ensure_future(started.wait())
            await asyncio.wait({waiter, entry.task}, timeout=queue_cap_s, return_when=asyncio.FIRST_COMPLETED)
            waiter.cancel()
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
