"""Vector search against Qdrant municipal-code collection.

Provides two retrieval modes:
1. semantic_search(query) — top-k similarity over chunk embeddings
2. get_by_section_id(section) — exact-match payload filter for cross-reference lookup

Uses raw HTTP API instead of qdrant-client to avoid version compatibility issues
between the Python client (1.18.x) and Qdrant server (1.9.x).
"""

from __future__ import annotations

import logging
import re
from functools import lru_cache
from typing import Any

import httpx

from backend.config import get_settings
from backend.models import CodeChunk


log = logging.getLogger(__name__)

MAX_CROSS_REF_HOPS = 1
MAX_CROSS_REF_PER_CHUNK = 3


@lru_cache
def _model():
    from sentence_transformers import SentenceTransformer

    settings = get_settings()
    log.info("Loading sentence-transformers model %s (cold start ~5s)", settings.embedding_model)
    return SentenceTransformer(settings.embedding_model)


def _qdrant_url() -> str:
    return get_settings().qdrant_url


def _payload_to_chunk(payload: dict[str, Any], score: float) -> CodeChunk:
    return CodeChunk(
        text=payload.get("text", ""),
        source_document=payload.get("source_document", "Chicago Municipal Code"),
        section=payload.get("section", ""),
        section_title=payload.get("section_title", ""),
        subsection=payload.get("subsection"),
        score=score,
        cross_references=payload.get("cross_references", []) or [],
    )


def semantic_search(query: str, *, top_k: int = 5, zoning_only: bool = False) -> list[CodeChunk]:
    settings = get_settings()
    collection = settings.qdrant_zoning_collection if zoning_only else settings.qdrant_code_collection
    vec = _model().encode(query, normalize_embeddings=True).tolist()
    try:
        resp = httpx.post(
            f"{_qdrant_url()}/collections/{collection}/points/search",
            json={"vector": vec, "limit": top_k, "with_payload": True},
            timeout=10.0,
        )
        resp.raise_for_status()
        hits = resp.json().get("result", [])
    except Exception as exc:
        log.warning("Qdrant query failed against %s: %s", collection, exc)
        return []
    return [_payload_to_chunk(h.get("payload", {}), h.get("score", 0.0)) for h in hits]


def get_by_section_id(section_id: str) -> CodeChunk | None:
    settings = get_settings()
    try:
        resp = httpx.post(
            f"{_qdrant_url()}/collections/{settings.qdrant_code_collection}/points/scroll",
            json={
                "filter": {"must": [{"key": "section", "match": {"value": section_id}}]},
                "limit": 1,
                "with_payload": True,
            },
            timeout=10.0,
        )
        resp.raise_for_status()
        points = resp.json().get("result", {}).get("points", [])
    except Exception as exc:
        log.warning("Qdrant scroll failed for %s: %s", section_id, exc)
        return None
    if not points:
        return None
    return _payload_to_chunk(points[0].get("payload", {}), score=1.0)


_PART_LABEL_RE = re.compile(r"\(part \d+ of \d+\)\n?")


def get_full_section(section_id: str) -> CodeChunk | None:
    """Fetch every chunk for a section and reassemble the complete text.

    Sections that exceed the chunker's size budget are split across multiple
    points (chunk_index 1..N), each carrying a repeated location header. We
    pull them all, order by chunk_index, keep the first chunk's header, strip
    the redundant header off parts 2+, and union their cross-references.
    """
    settings = get_settings()
    try:
        resp = httpx.post(
            f"{_qdrant_url()}/collections/{settings.qdrant_code_collection}/points/scroll",
            json={
                "filter": {"must": [{"key": "section", "match": {"value": section_id}}]},
                "limit": 64,
                "with_payload": True,
            },
            timeout=10.0,
        )
        resp.raise_for_status()
        points = resp.json().get("result", {}).get("points", [])
    except Exception as exc:
        log.warning("Qdrant scroll failed for full section %s: %s", section_id, exc)
        return None
    if not points:
        return None

    payloads = [p.get("payload", {}) for p in points]
    payloads.sort(key=lambda p: p.get("chunk_index", 1))

    parts = [payloads[0].get("text", "")]
    for p in payloads[1:]:
        text = p.get("text", "")
        # Drop the repeated location header (everything up to the first blank line).
        body = text.split("\n\n", 1)
        parts.append(body[1] if len(body) > 1 else text)
    merged = _PART_LABEL_RE.sub("", "\n\n".join(part for part in parts if part))

    seen: set[str] = set()
    refs: list[str] = []
    for p in payloads:
        for ref in p.get("cross_references", []) or []:
            if ref not in seen:
                seen.add(ref)
                refs.append(ref)

    base = payloads[0]
    return CodeChunk(
        text=merged,
        source_document=base.get("source_document", "Chicago Municipal Code"),
        section=base.get("section", section_id),
        section_title=base.get("section_title", ""),
        subsection=base.get("subsection"),
        score=1.0,
        cross_references=refs,
    )


_SECTION_REF_RE = re.compile(r"^\d+-\d+-\d+(?:\.\d+)?$")


def expand_cross_references(chunks: list[CodeChunk]) -> list[CodeChunk]:
    """One-hop expansion: pull referenced sections by exact ID, dedupe by section.

    Cross-references stored in payload may also include Title/Chapter anchors
    (e.g. 'Title17', 'Ch.17-2'); only true section IDs are resolvable here, so
    everything else is silently skipped.
    """
    seen: set[str] = {c.section for c in chunks}
    extras: list[CodeChunk] = []
    for chunk in chunks:
        pulled = 0
        for ref in chunk.cross_references:
            if pulled >= MAX_CROSS_REF_PER_CHUNK:
                break
            if ref in seen or not _SECTION_REF_RE.match(ref):
                continue
            referenced = get_by_section_id(ref)
            if referenced:
                referenced.score = min(chunk.score, 0.5)
                extras.append(referenced)
                seen.add(ref)
                pulled += 1
    return chunks + extras
