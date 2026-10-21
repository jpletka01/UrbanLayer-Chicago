"""Copy, verify and switch Municipal Code collections between Qdrant instances.

Each vintage of the code lives in its own collection (``municipal_code_<vintage>``) and
the app reads the alias ``municipal_code``. A refresh embeds locally, copies the finished
collection to prod (vectors, payloads and ids, so nothing is re-embedded on the 8 GB
box), proves the copy equals local, then flips the alias in one atomic call. Rollback is
the same flip back to the previous collection, which stays until the next refresh.

    # prod is reached through an SSH tunnel (see claude-context/guides/deployment.md)
    python -m ingestion.push_index --target http://localhost:6335 --status
    python -m ingestion.push_index --target http://localhost:6335 --upload
    python -m ingestion.push_index --target http://localhost:6335 --verify
    python -m ingestion.push_index --target http://localhost:6335 --switch
    python -m ingestion.push_index --target http://localhost:6335 --switch --to municipal_code_2026-03-18
    # server-side copy of a collection under a new name (snapshot + recover, no transfer)
    python -m ingestion.push_index --target http://localhost:6335 --snapshot-copy chicago_municipal_code \
        --collection municipal_code_2026-03-18
    python -m ingestion.push_index --target http://localhost:6335 --drop chicago_municipal_code

``--collection`` defaults to the collection the local alias points at. ``--verify``
compares, section by section, the multiset of chunk-text hashes in the source collection
with the target's; ``--switch`` (without ``--to``) refuses unless that reports 0
differences.
"""

from __future__ import annotations

import argparse
import hashlib
import logging
import sys
from collections import Counter
from dataclasses import dataclass, field

from qdrant_client import QdrantClient
from qdrant_client.models import (
    CreateAlias,
    CreateAliasOperation,
    DeleteAlias,
    DeleteAliasOperation,
    PointStruct,
    VectorParams,
)

from .code_vintage import CODE_ALIAS


log = logging.getLogger(__name__)

PAGE = 256
# Where Qdrant keeps snapshots inside its container (the image default).
SNAPSHOTS_DIR = "/qdrant/snapshots"


def alias_target(client: QdrantClient, alias: str = CODE_ALIAS) -> str | None:
    for a in client.get_aliases().aliases:
        if a.alias_name == alias:
            return a.collection_name
    return None


def _collections(client: QdrantClient) -> set[str]:
    return {c.name for c in client.get_collections().collections}


def switch_alias(client: QdrantClient, collection: str, alias: str = CODE_ALIAS) -> str | None:
    """Point ``alias`` at ``collection`` in one call; returns the previous target."""
    if collection not in _collections(client):
        raise ValueError(f"No collection {collection!r} to point {alias!r} at")
    previous = alias_target(client, alias)
    ops: list = []
    if previous is not None:
        ops.append(DeleteAliasOperation(delete_alias=DeleteAlias(alias_name=alias)))
    ops.append(
        CreateAliasOperation(create_alias=CreateAlias(collection_name=collection, alias_name=alias))
    )
    client.update_collection_aliases(change_aliases_operations=ops)
    return previous


def _scroll(client: QdrantClient, collection: str, *, with_vectors: bool, payload=True):
    offset = None
    while True:
        points, offset = client.scroll(
            collection, limit=PAGE, offset=offset, with_payload=payload, with_vectors=with_vectors
        )
        yield from points
        if offset is None:
            return


def upload(
    source: QdrantClient, target: QdrantClient, collection: str, *, replace: bool = False
) -> int:
    """Copy ``collection`` from source to target under the same name. Returns points copied."""
    info = source.get_collection(collection)
    vectors = info.config.params.vectors
    if not isinstance(vectors, VectorParams):
        raise ValueError(f"{collection}: only a single unnamed vector is supported")
    if collection in _collections(target):
        if target.count(collection, exact=True).count and not replace:
            raise SystemExit(
                f"{collection} already exists on the target and is not empty "
                "(pass --replace to rebuild it)"
            )
        if collection == alias_target(target):
            raise SystemExit(f"{collection} is what the target's alias serves; refusing to rebuild it")
        target.delete_collection(collection)
    target.create_collection(
        collection, vectors_config=VectorParams(size=vectors.size, distance=vectors.distance)
    )
    total = 0
    batch: list[PointStruct] = []
    for p in _scroll(source, collection, with_vectors=True):
        batch.append(PointStruct(id=p.id, vector=p.vector, payload=p.payload))
        if len(batch) >= PAGE:
            target.upsert(collection, points=batch, wait=True)
            total += len(batch)
            batch = []
            if total % (PAGE * 16) == 0:
                log.info("Uploaded %d points", total)
    if batch:
        target.upsert(collection, points=batch, wait=True)
        total += len(batch)
    log.info("Uploaded %d points to %s", total, collection)
    return total


def section_hashes(client: QdrantClient, collection: str) -> dict[str, Counter]:
    """{section id: multiset of sha256(chunk text)} for every point in ``collection``."""
    out: dict[str, Counter] = {}
    for p in _scroll(client, collection, with_vectors=False, payload=["section", "text"]):
        payload = p.payload or {}
        digest = hashlib.sha256((payload.get("text") or "").encode()).hexdigest()
        out.setdefault(payload.get("section") or "", Counter())[digest] += 1
    return out


@dataclass
class VerifyResult:
    source_points: int
    target_points: int
    differing_sections: dict[str, tuple[int, int]] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not self.differing_sections and self.source_points == self.target_points


def verify(
    source: QdrantClient, source_collection: str, target: QdrantClient, target_collection: str
) -> VerifyResult:
    a = section_hashes(source, source_collection)
    b = section_hashes(target, target_collection)
    result = VerifyResult(
        source_points=sum(sum(c.values()) for c in a.values()),
        target_points=sum(sum(c.values()) for c in b.values()),
    )
    for sid in sorted(set(a) | set(b)):
        ca, cb = a.get(sid, Counter()), b.get(sid, Counter())
        if ca != cb:
            result.differing_sections[sid] = (sum(ca.values()), sum(cb.values()))
    return result


def snapshot_copy(client: QdrantClient, source_collection: str, new_collection: str) -> int:
    """Copy a collection to a new name on the SAME server (snapshot, then recover from it).

    Nothing crosses the network but the API calls. The snapshot is deleted afterwards.
    """
    if new_collection in _collections(client):
        raise SystemExit(f"{new_collection} already exists")
    snap = client.create_snapshot(source_collection, wait=True)
    if snap is None:
        raise SystemExit(f"Snapshot of {source_collection} failed")
    location = f"file://{SNAPSHOTS_DIR}/{source_collection}/{snap.name}"
    log.info("Recovering %s from %s", new_collection, location)
    try:
        client.recover_snapshot(new_collection, location=location, wait=True)
    finally:
        client.delete_snapshot(source_collection, snap.name, wait=True)
    count = client.count(new_collection, exact=True).count
    log.info("%s now has %d points", new_collection, count)
    return count


def drop(client: QdrantClient, collection: str) -> None:
    for a in client.get_aliases().aliases:
        if a.collection_name == collection:
            raise SystemExit(f"Alias {a.alias_name!r} still points at {collection}; switch it first")
    client.delete_collection(collection)


def status(client: QdrantClient) -> list[str]:
    lines = []
    aliases = {a.alias_name: a.collection_name for a in client.get_aliases().aliases}
    for name in sorted(_collections(client)):
        served = [al for al, c in aliases.items() if c == name]
        tag = f"  <- {', '.join(served)}" if served else ""
        lines.append(f"{name}: {client.count(name, exact=True).count} points{tag}")
    return lines


def _client(url: str) -> QdrantClient:
    return QdrantClient(url=url, timeout=120, check_compatibility=False)


def main(argv: list[str] | None = None) -> int:
    from backend.config import get_settings

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--target", required=True, help="Target Qdrant URL (prod via tunnel)")
    parser.add_argument("--source", default=None, help="Source Qdrant URL (default: settings.qdrant_url)")
    parser.add_argument("--collection", default=None, help="Collection to push/verify/switch to "
                        "(default: what the source's alias points at)")
    parser.add_argument("--target-collection", default=None,
                        help="--verify: compare against this target collection instead of the same name")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--status", action="store_true")
    mode.add_argument("--upload", action="store_true")
    mode.add_argument("--verify", action="store_true")
    mode.add_argument("--switch", action="store_true")
    mode.add_argument("--snapshot-copy", metavar="FROM", default=None)
    mode.add_argument("--drop", metavar="NAME", default=None)
    parser.add_argument("--to", default=None, help="--switch: roll back to this collection (skips verify)")
    parser.add_argument("--replace", action="store_true", help="--upload: rebuild an existing target collection")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    target = _client(args.target)

    if args.status:
        print("\n".join(status(target)) or "(no collections)")
        return 0
    if args.drop:
        drop(target, args.drop)
        log.info("Dropped %s", args.drop)
        return 0
    if args.snapshot_copy:
        if not args.collection:
            parser.error("--snapshot-copy needs --collection (the new name)")
        snapshot_copy(target, args.snapshot_copy, args.collection)
        return 0
    if args.switch and args.to:
        previous = switch_alias(target, args.to)
        log.info("%s: %s -> %s (rollback, not verified)", CODE_ALIAS, previous, args.to)
        return 0

    source = _client(args.source or get_settings().qdrant_url)
    collection = args.collection or alias_target(source)
    if not collection:
        parser.error(f"source has no {CODE_ALIAS!r} alias; pass --collection")

    if args.upload:
        upload(source, target, collection, replace=args.replace)
        return 0

    result = verify(source, collection, target, args.target_collection or collection)
    log.info(
        "Verify %s: source %d points, target %d points, %d section(s) differ",
        collection, result.source_points, result.target_points, len(result.differing_sections),
    )
    for sid, (a, b) in list(result.differing_sections.items())[:25]:
        log.warning("  %s: source %d chunks, target %d (text hashes differ)", sid or "(no section)", a, b)
    if not result.ok:
        if args.switch:
            log.error("Not switching: the target collection differs from the source")
        return 1
    if args.switch:
        previous = switch_alias(target, collection)
        log.info("%s: %s -> %s", CODE_ALIAS, previous, collection)
    return 0


if __name__ == "__main__":
    sys.exit(main())
