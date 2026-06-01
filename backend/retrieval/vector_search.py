"""Vector search against Qdrant municipal-code collection.

Provides two retrieval modes:
1. semantic_search(query) — top-k similarity over chunk embeddings
2. get_by_section_id(section) — exact-match payload filter for cross-reference lookup

Uses raw HTTP API instead of qdrant-client to avoid version compatibility issues
between the Python client (1.18.x) and Qdrant server (1.9.x).

All public functions are async. CPU-bound operations (embedding encode,
cross-encoder predict) run in a thread pool via run_in_executor.
"""

from __future__ import annotations

import asyncio
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

_known_sections_cache: frozenset[str] | None = None
_known_sections_lock = asyncio.Lock()


async def _get_known_sections() -> frozenset[str]:
    """Scroll all Qdrant points once and cache the set of section IDs."""
    global _known_sections_cache
    if _known_sections_cache is not None:
        return _known_sections_cache
    async with _known_sections_lock:
        if _known_sections_cache is not None:
            return _known_sections_cache
        settings = get_settings()
        sections: set[str] = set()
        offset = None
        async with httpx.AsyncClient(timeout=30.0) as client:
            while True:
                body: dict[str, Any] = {
                    "limit": 1000,
                    "with_payload": {"include": ["section"]},
                }
                if offset is not None:
                    body["offset"] = offset
                try:
                    resp = await client.post(
                        f"{settings.qdrant_url}/collections/{settings.qdrant_code_collection}/points/scroll",
                        json=body,
                    )
                    resp.raise_for_status()
                    result = resp.json().get("result", {})
                except Exception as exc:
                    log.warning("Failed to build section index: %s", exc)
                    return frozenset()
                for point in result.get("points", []):
                    s = point.get("payload", {}).get("section", "")
                    if s:
                        sections.add(s)
                offset = result.get("next_page_offset")
                if offset is None:
                    break
        _known_sections_cache = frozenset(sections)
        log.info("Section index built: %d unique sections", len(_known_sections_cache))
        return _known_sections_cache

_LEGEND_RE = re.compile(
    r"Row \d+ \(all columns\):.*(?:permitted|special use|planned development|[Nn]ot allowed)",
)
_REGULAR_ROW_RE = re.compile(r"^Row \d+: ", re.MULTILINE)


def _is_legend_only_chunk(text: str) -> bool:
    """Return True if the chunk is a table legend/key with no real data rows.

    Legend chunks contain only ``Row N (all columns): P = permitted ...``
    entries and no actual ``Row N: header: value; ...`` data rows.
    """
    if "[TABLE]" not in text:
        return False
    if not _LEGEND_RE.search(text):
        return False
    return not _REGULAR_ROW_RE.search(text)


_STOPWORDS = frozenset({
    "a", "an", "the", "in", "on", "at", "to", "for", "of", "and", "or",
    "is", "are", "was", "were", "be", "been", "being", "have", "has", "had",
    "do", "does", "did", "will", "would", "could", "should", "may", "might",
    "can", "i", "my", "me", "we", "our", "you", "your", "it", "its", "they",
    "them", "their", "this", "that", "what", "which", "who", "how", "when",
    "where", "not", "no", "if", "but", "so", "from", "with", "by", "about",
})
_WORD_RE = re.compile(r"[a-z0-9]+(?:[-'][a-z0-9]+)*")


@lru_cache
def _model():
    from sentence_transformers import SentenceTransformer

    settings = get_settings()
    log.info("Loading sentence-transformers model %s", settings.embedding_model)
    return SentenceTransformer(settings.embedding_model)


@lru_cache(maxsize=1)
def _reranker():
    from sentence_transformers import CrossEncoder

    settings = get_settings()
    log.info("Loading cross-encoder model %s", settings.reranker_model)
    return CrossEncoder(settings.reranker_model)


def _keyword_score(query: str, text: str) -> float:
    """Fraction of unique non-stopword query terms found in the text."""
    query_terms = {w for w in _WORD_RE.findall(query.lower()) if w not in _STOPWORDS}
    if not query_terms:
        return 0.0
    text_lower = text.lower()
    return sum(1 for t in query_terms if t in text_lower) / len(query_terms)


def _rerank_payloads_sync(
    query: str,
    scored_hits: list[tuple[float, dict[str, Any]]],
) -> list[tuple[float, dict[str, Any]]]:
    """Blend dense+keyword scores with cross-encoder scores (CPU-bound)."""
    if not scored_hits:
        return scored_hits
    settings = get_settings()
    reranker = _reranker()
    texts = [p.get("text", "") for _, p in scored_hits]
    pairs = [[query, t] for t in texts]
    raw_scores = reranker.predict(pairs)

    rmin, rmax = float(min(raw_scores)), float(max(raw_scores))
    r_range = rmax - rmin if rmax > rmin else 1.0
    omin = min(s for s, _ in scored_hits)
    omax = max(s for s, _ in scored_hits)
    o_range = omax - omin if omax > omin else 1.0

    w = settings.reranker_weight
    result = []
    for (orig_score, payload), rs in zip(scored_hits, raw_scores):
        norm_r = (float(rs) - rmin) / r_range
        norm_o = (orig_score - omin) / o_range
        final = round((1 - w) * norm_o + w * norm_r, 4)
        result.append((final, payload))
    return result


def _qdrant_url() -> str:
    return get_settings().qdrant_url


def _payload_to_chunk(
    payload: dict[str, Any],
    score: float,
    known_sections: frozenset[str] = frozenset(),
) -> CodeChunk:
    refs = payload.get("cross_references", []) or []
    if known_sections:
        refs = [r for r in refs if r in known_sections]
    return CodeChunk(
        text=payload.get("text", ""),
        source_document=payload.get("source_document", "Chicago Municipal Code"),
        section=payload.get("section", ""),
        section_title=payload.get("section_title", ""),
        subsection=payload.get("subsection"),
        score=score,
        cross_references=refs,
    )


async def semantic_search(query: str, *, top_k: int = 5, zoning_only: bool = False) -> list[CodeChunk]:
    settings = get_settings()
    collection = settings.qdrant_zoning_collection if zoning_only else settings.qdrant_code_collection

    loop = asyncio.get_running_loop()
    prefixed = settings.embedding_query_prefix + query
    vec = await loop.run_in_executor(
        None, lambda: _model().encode(prefixed, normalize_embeddings=True).tolist()
    )

    rerank = settings.reranker_enabled
    candidate_count = settings.reranker_candidate_count if rerank else top_k
    fetch_limit = max(top_k * 5, candidate_count * 3)

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.post(
                f"{_qdrant_url()}/collections/{collection}/points/search",
                json={"vector": vec, "limit": fetch_limit, "with_payload": True},
            )
            resp.raise_for_status()
            hits = resp.json().get("result", [])
        except Exception as exc:
            log.warning("Qdrant query failed against %s: %s", collection, exc)
            return []

    kw_weight = settings.keyword_boost_weight
    scored_hits = []
    for h in hits:
        payload = h.get("payload", {})
        if _is_legend_only_chunk(payload.get("text", "")):
            continue
        dense = h.get("score", 0.0)
        if kw_weight > 0:
            kw = _keyword_score(query, payload.get("text", ""))
            combined = (1 - kw_weight) * dense + kw_weight * kw
        else:
            combined = dense
        scored_hits.append((combined, payload))

    if rerank and len(scored_hits) > top_k:
        scored_hits = await loop.run_in_executor(
            None, lambda: _rerank_payloads_sync(query, scored_hits)
        )

    scored_hits.sort(key=lambda x: x[0], reverse=True)

    known = await _get_known_sections()
    chunks = []
    seen_sections: set[str] = set()
    for score, payload in scored_hits:
        section = payload.get("section", "")
        if section in seen_sections:
            continue
        seen_sections.add(section)
        chunks.append(_payload_to_chunk(payload, score, known))
        if len(chunks) >= top_k:
            break

    return chunks


async def get_by_section_id(section_id: str) -> CodeChunk | None:
    settings = get_settings()
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.post(
                f"{_qdrant_url()}/collections/{settings.qdrant_code_collection}/points/scroll",
                json={
                    "filter": {"must": [{"key": "section", "match": {"value": section_id}}]},
                    "limit": 1,
                    "with_payload": True,
                },
            )
            resp.raise_for_status()
            points = resp.json().get("result", {}).get("points", [])
        except Exception as exc:
            log.warning("Qdrant scroll failed for %s: %s", section_id, exc)
            return None
    if not points:
        return None
    known = await _get_known_sections()
    return _payload_to_chunk(points[0].get("payload", {}), score=1.0, known_sections=known)


_PART_LABEL_RE = re.compile(r"\(part \d+ of \d+\)\n?")


async def get_full_section(section_id: str) -> CodeChunk | None:
    """Fetch every chunk for a section and reassemble the complete text.

    Sections that exceed the chunker's size budget are split across multiple
    points (chunk_index 1..N), each carrying a repeated location header. We
    pull them all, order by chunk_index, keep the first chunk's header, strip
    the redundant header off parts 2+, and union their cross-references.
    """
    settings = get_settings()
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.post(
                f"{_qdrant_url()}/collections/{settings.qdrant_code_collection}/points/scroll",
                json={
                    "filter": {"must": [{"key": "section", "match": {"value": section_id}}]},
                    "limit": 64,
                    "with_payload": True,
                },
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
        body = text.split("\n\n", 1)
        parts.append(body[1] if len(body) > 1 else text)
    merged = _PART_LABEL_RE.sub("", "\n\n".join(part for part in parts if part))

    known = await _get_known_sections()
    seen: set[str] = set()
    refs: list[str] = []
    for p in payloads:
        for ref in p.get("cross_references", []) or []:
            if ref not in seen:
                seen.add(ref)
                if not known or ref in known:
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


_SECTION_REF_RE = re.compile(r"^\d+[A-Za-z]?-\d+-\d+")


async def get_by_section_ids_batch(section_ids: list[str]) -> dict[str, CodeChunk]:
    """Fetch multiple sections in a single Qdrant scroll call."""
    if not section_ids:
        return {}
    settings = get_settings()
    filter_body = {
        "should": [
            {"key": "section", "match": {"value": sid}}
            for sid in section_ids
        ]
    }
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.post(
                f"{_qdrant_url()}/collections/{settings.qdrant_code_collection}/points/scroll",
                json={
                    "filter": filter_body,
                    "limit": len(section_ids),
                    "with_payload": True,
                },
            )
            resp.raise_for_status()
            points = resp.json().get("result", {}).get("points", [])
        except Exception as exc:
            log.warning("Qdrant batch scroll failed: %s", exc)
            return {}
    known = await _get_known_sections()
    result: dict[str, CodeChunk] = {}
    for point in points:
        payload = point.get("payload", {})
        sid = payload.get("section", "")
        if sid and sid not in result:
            result[sid] = _payload_to_chunk(payload, score=1.0, known_sections=known)
    return result


async def expand_cross_references(chunks: list[CodeChunk]) -> list[CodeChunk]:
    """One-hop expansion: pull referenced sections by exact ID, dedupe by section.

    Cross-references stored in payload may also include Title/Chapter anchors
    (e.g. 'Title17', 'Ch.17-2'); only true section IDs are resolvable here, so
    everything else is silently skipped.
    """
    seen: set[str] = {c.section for c in chunks}
    needed: dict[str, float] = {}
    for chunk in chunks:
        pulled = 0
        for ref in chunk.cross_references:
            if pulled >= MAX_CROSS_REF_PER_CHUNK:
                break
            if ref in seen or not _SECTION_REF_RE.match(ref):
                continue
            if ref not in needed:
                needed[ref] = min(chunk.score, 0.5)
            seen.add(ref)
            pulled += 1

    if not needed:
        return chunks

    fetched = await get_by_section_ids_batch(list(needed.keys()))
    extras: list[CodeChunk] = []
    for ref, score in needed.items():
        if ref in fetched:
            chunk = fetched[ref]
            chunk.score = score
            extras.append(chunk)
    return chunks + extras
