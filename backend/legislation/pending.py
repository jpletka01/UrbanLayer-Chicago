"""Build the dark WS2 snapshot of pending zoning legislation.

This module is sync-only.  It reads the public Clerk API, resolves the current member of
each original/substitute lifecycle, removes EDS and non-allowlisted attachment metadata,
and hands one normalized snapshot to :mod:`pending_store`.  It never downloads a PDF and
never calls a model.

    python -m backend.legislation.pending --print   # query + summarize, write nothing
    python -m backend.legislation.pending           # replace the configured local store
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import re
import sqlite3
import sys
from collections import defaultdict, deque
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import TypeAlias

import httpx

from backend.config import get_settings
from backend.legislation import address_titles
from backend.legislation.pending_store import (
    ActionRow,
    AttachmentRow,
    MatterRow,
    RelationRow,
    Snapshot,
    Store,
)
from backend.retrieval import clerk


log = logging.getLogger(__name__)

ALLOWED_ATTACHMENT_TYPES = frozenset({"Legislation", "Exhibits", "Miscellaneous", "Committee Letter"})
_EDS = re.compile(r"\bEDS\b|ECONOMIC\s+DISCLOS", re.IGNORECASE)
_RECORD = re.compile(r"^S?O\d{4}-\d+$", re.IGNORECASE)
# The public Clerk API began returning 429 after roughly a minute of the first full
# audit. Four detail requests/second keeps this once-daily job comfortably below that
# observed burst while the shared client still handles a server-directed retry.
_DETAIL_PAUSE_S = 0.25
_sleep = asyncio.sleep

DetailById: TypeAlias = Callable[..., Awaitable[clerk.ClerkMatter | None]]
DetailByRecord: TypeAlias = Callable[..., Awaitable[clerk.ClerkMatter | None]]
PendingSearch: TypeAlias = Callable[..., Awaitable[list[clerk.ClerkMatter]]]
# Named seam for the hermetic suite: conftest replaces this default with an empty
# recorded world, while focused tests pass their own search/detail callables.
search_pending: PendingSearch = clerk.pending_zoning_matters


class PendingContractError(Exception):
    """The feed answered, but its lifecycle/status contract is no longer safe."""

    def __init__(self, problems: list[str] | tuple[str, ...]):
        self.problems = tuple(problems)
        super().__init__("; ".join(self.problems))


def _is_eds(file_name: str, attachment_type: str) -> bool:
    return bool(_EDS.search(f"{attachment_type} {file_name}"))


def attachment_allowed(attachment: clerk.ClerkAttachment) -> bool:
    """Only expected public-document metadata; EDS is rejected before persistence."""
    return (
        attachment.type in ALLOWED_ATTACHMENT_TYPES
        and not _is_eds(attachment.file_name, attachment.type)
        and attachment.url.startswith("https://")
    )


def _record_base(value: str) -> str:
    value = value.upper()
    return value[1:] if value.startswith("SO") else value


def _same_lifecycle(left: str, right: str) -> bool:
    return bool(_RECORD.match(left) and _RECORD.match(right) and _record_base(left) == _record_base(right))


def _detail_status_problem(matter: clerk.ClerkMatter) -> str | None:
    if matter.status == clerk.FINAL:
        if matter.sub_status not in clerk.KNOWN_FINAL_SUBSTATUSES:
            return f"unknown final subStatus {matter.sub_status!r} on {matter.record_number}"
        return None
    if matter.status not in clerk.KNOWN_PENDING_STATUSES:
        return f"unknown pending status {matter.status!r} on {matter.record_number}"
    if matter.sub_status not in clerk.KNOWN_PENDING_SUBSTATUSES:
        return f"unknown pending subStatus {matter.sub_status!r} on {matter.record_number}"
    return None


class _UnionFind:
    def __init__(self) -> None:
        self.parent: dict[str, str] = {}

    def find(self, value: str) -> str:
        self.parent.setdefault(value, value)
        if self.parent[value] != value:
            self.parent[value] = self.find(self.parent[value])
        return self.parent[value]

    def union(self, left: str, right: str) -> None:
        a, b = self.find(left), self.find(right)
        if a != b:
            self.parent[b] = a


async def _call_lookup(fn, value: str, client: httpx.AsyncClient | None) -> clerk.ClerkMatter | None:
    return await fn(value, client=client)


async def _full_details(
    listed: list[clerk.ClerkMatter],
    *,
    client: httpx.AsyncClient | None,
    detail_by_id: DetailById,
    detail_by_record: DetailByRecord,
    pause_s: float,
) -> dict[str, clerk.ClerkMatter]:
    """Fetch every listed detail plus explicit substitute/supersession links, serially."""
    queue: deque[tuple[str, str, bool]] = deque(
        ("id", matter.matter_id, True) for matter in listed
    )
    seen_ids: set[str] = set()
    seen_records: set[str] = set()
    details: dict[str, clerk.ClerkMatter] = {}
    requests = 0

    while queue:
        kind, value, required = queue.popleft()
        if kind == "id":
            if value in seen_ids:
                continue
            seen_ids.add(value)
            detail = await _call_lookup(detail_by_id, value, client)
        else:
            if value in seen_records:
                continue
            seen_records.add(value)
            detail = await _call_lookup(detail_by_record, value, client)
        requests += 1
        if detail is None:
            if required:
                raise PendingContractError([f"Clerk detail {value!r} disappeared during the pending refresh"])
            continue

        details[detail.matter_id] = detail
        seen_ids.add(detail.matter_id)
        if detail.superseded_by and detail.superseded_by != detail.record_number:
            queue.append(("record", detail.superseded_by, True))
        for related in detail.relations:
            if related not in {detail.record_number, detail.original_record_number} and _RECORD.match(related):
                queue.append(("record", related, False))
        if pause_s and queue:
            await _sleep(pause_s)

    log.info("pending legislation detail refresh: %d request(s), %d unique matter(s)", requests, len(details))
    return details


def _relations(group: list[clerk.ClerkMatter], current: clerk.ClerkMatter) -> tuple[RelationRow, ...]:
    found: set[tuple[str, str]] = set()
    for matter in group:
        if matter.original_record_number and matter.original_record_number != current.record_number:
            found.add((matter.original_record_number, "original"))
        if matter.superseded_by:
            found.add((matter.superseded_by, "superseded_by"))
        for related in matter.relations:
            if related != current.record_number:
                found.add((related, "api_relation"))
        if matter.record_number != current.record_number:
            found.add((matter.record_number, "lifecycle_member"))
    return tuple(RelationRow(record, kind) for record, kind in sorted(found))


def _normalize(details: dict[str, clerk.ClerkMatter], *, now: datetime, candidate_count: int) -> Snapshot:
    problems = [p for matter in details.values() if (p := _detail_status_problem(matter))]
    if problems:
        raise PendingContractError(sorted(set(problems)))

    uf = _UnionFind()
    for matter in details.values():
        uf.find(matter.record_number)
        if matter.original_record_number:
            uf.union(matter.record_number, matter.original_record_number)
        if matter.superseded_by:
            uf.union(matter.record_number, matter.superseded_by)
        for related in matter.relations:
            if _same_lifecycle(matter.record_number, related):
                uf.union(matter.record_number, related)

    groups: dict[str, list[clerk.ClerkMatter]] = defaultdict(list)
    for matter in details.values():
        groups[uf.find(matter.record_number)].append(matter)

    rows: list[MatterRow] = []
    excluded_non_pending = 0
    excluded_attachments = 0
    lifecycle_collapses = 0
    placement_ready = 0
    partial_titles = 0
    unparsed_titles = 0

    for group in groups.values():
        lifecycle_collapses += max(0, len(group) - 1)
        active = [
            matter for matter in group
            if matter.status in clerk.KNOWN_PENDING_STATUSES and not matter.superseded_by
        ]
        excluded_non_pending += sum(1 for matter in group if matter.status == clerk.FINAL or matter.superseded_by)
        if not active:
            continue
        if len(active) > 1:
            records = ", ".join(sorted(m.record_number for m in active))
            raise PendingContractError([f"multiple current matters in one lifecycle: {records}"])
        current = active[0]

        identifiers = {
            value for matter in group
            for value in (matter.original_record_number, matter.record_number)
            if value
        }
        originals = sorted(value for value in identifiers if value.startswith("O"))
        lifecycle_id = originals[0] if originals else current.record_number

        parsed = None
        if current.category.startswith(clerk.ZONING_RECLASSIFICATIONS):
            parsed = address_titles.parse_title(current.title)
            if parsed.status == "clean":
                placement_ready += 1
            elif parsed.status == "partial":
                partial_titles += 1
            else:
                unparsed_titles += 1

        kept_attachments = tuple(
            AttachmentRow(a.file_name, a.url, a.type)
            for a in current.attachments if attachment_allowed(a)
        )
        excluded_attachments += len(current.attachments) - len(kept_attachments)
        rows.append(MatterRow(
            matter_id=current.matter_id,
            lifecycle_id=lifecycle_id,
            record_number=current.record_number,
            original_record_number=current.original_record_number,
            status=current.status,
            sub_status=current.sub_status,
            category=current.category,
            matter_type=current.type,
            title=current.title,
            introduced_at=current.introduced_at,
            created_at=current.created_at,
            last_published_at=current.last_published_at,
            superseded_by=current.superseded_by,
            source_url=current.url,
            title_parse_status=parsed.status if parsed else None,
            application_number=parsed.app_no if parsed else None,
            touches_title17=(current.category.startswith(clerk.CODE_AMENDMENTS) and clerk.touches_title17(current.title)),
            actions=tuple(ActionRow(a.date, a.body, a.name, a.text, a.meeting_id) for a in current.actions),
            attachments=kept_attachments,
            relations=_relations(group, current),
        ))

    rows.sort(key=lambda row: (row.category, row.introduced_at or datetime.min.replace(tzinfo=timezone.utc), row.record_number))
    return Snapshot(
        checked_at=now,
        matters=tuple(rows),
        candidate_count=candidate_count,
        detail_count=len(details),
        lifecycle_collapses=lifecycle_collapses,
        excluded_non_pending=excluded_non_pending,
        excluded_attachments=excluded_attachments,
        placement_ready_count=placement_ready,
        partial_title_count=partial_titles,
        unparsed_title_count=unparsed_titles,
    )


async def build_snapshot(
    *,
    now: datetime | None = None,
    client: httpx.AsyncClient | None = None,
    search: PendingSearch | None = None,
    detail_by_id: DetailById | None = None,
    detail_by_record: DetailByRecord | None = None,
    pause_s: float = _DETAIL_PAUSE_S,
) -> Snapshot:
    """Read and normalize the current pending feed without writing anything."""
    now = now or datetime.now(timezone.utc)
    search = search or search_pending
    detail_by_id = detail_by_id or clerk.get_matter
    detail_by_record = detail_by_record or clerk.get_matter_by_record
    listed = await search(client=client)
    log.info("pending legislation list refresh: %d candidate(s)", len(listed))
    details = await _full_details(
        listed,
        client=client,
        detail_by_id=detail_by_id,
        detail_by_record=detail_by_record,
        pause_s=pause_s,
    )
    return _normalize(details, now=now, candidate_count=len(listed))


async def refresh(
    path: Path,
    *,
    write: bool = True,
    now: datetime | None = None,
    client: httpx.AsyncClient | None = None,
    **build_kwargs,
) -> Snapshot:
    """Build the snapshot and, when requested, atomically replace the store."""
    now = now or datetime.now(timezone.utc)
    try:
        snapshot = await build_snapshot(now=now, client=client, **build_kwargs)
        if write:
            with Store(path) as store:
                store.replace(snapshot)
        return snapshot
    except (PendingContractError, clerk.ClerkContractError) as exc:
        if write:
            with Store(path) as store:
                problems = exc.problems if isinstance(exc, PendingContractError) else (str(exc),)
                store.record_problem(now, status="suspect", error=str(exc), contract_problems=tuple(problems))
        raise
    except (clerk.ClerkUnavailable, clerk.ClerkQueryError, sqlite3.Error) as exc:
        if write:
            with Store(path) as store:
                store.record_problem(now, status="failed", error=f"{type(exc).__name__}: {exc}")
        raise


def summary(snapshot: Snapshot) -> str:
    c = snapshot.counts
    return (
        f"candidates={c['candidates']} details={c['details']} pending={c['pending']} "
        f"zoning={c['zoning']} title17={c['title17']} "
        f"placement_ready={c['placement_ready']} partial={c['partial_titles']} "
        f"unparsed={c['unparsed_titles']} lifecycle_collapses={c['lifecycle_collapses']} "
        f"excluded_non_pending={c['excluded_non_pending']} excluded_attachments={c['excluded_attachments']}"
    )


async def _main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Refresh the pending City Clerk zoning snapshot")
    parser.add_argument("--print", action="store_true", help="query and summarize; write nothing")
    parser.add_argument("--out", type=Path, help="write here instead of settings.pending_legislation_path")
    args = parser.parse_args(argv)
    path = args.out or get_settings().pending_legislation_path
    try:
        snapshot = await refresh(path, write=not args.print)
    except (PendingContractError, clerk.ClerkUnavailable, clerk.ClerkQueryError, sqlite3.Error) as exc:
        print(f"pending legislation: failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    print(f"checked_at={snapshot.checked_at.isoformat()} {summary(snapshot)}")
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    sys.exit(asyncio.run(_main(sys.argv[1:])))
