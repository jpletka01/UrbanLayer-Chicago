"""Extract structured zoning standards from Municipal Code via Haiku.

Runs 5 targeted vector searches for a given zone class, then uses Claude Haiku
to extract structured parameters (FAR, height, setbacks, uses, parking) into
a ZoningStandards model.
"""

import asyncio
import json
import logging
import re
from typing import Any

from backend.config import get_settings
from backend.llm import tracked_create
from backend.models import DevelopmentPotential, ZoningStandards
from backend.retrieval.vector_search import get_full_section, semantic_search

log = logging.getLogger(__name__)


def _height_ft_from_definition(max_height: str | None) -> int | None:
    """Numeric as-of-right height floor from a ZoneDefinition display string.

    Height strings lead with the LOWEST tier of frontage-dependent ranges
    ("45–47 ft (varies by lot frontage)" → 45) so the number that flows into
    calculations is true everywhere in the district. Digit-free strings
    ("No fixed cap — tall buildings require PD review") parse to None. The
    anchor matters: an unanchored search would pull digits out of prose.
    """
    if not max_height:
        return None
    m = re.match(r"\s*(\d+)", max_height)
    return int(m.group(1)) if m else None


def apply_table_authority(standards: ZoningStandards, zone_class: str) -> ZoningStandards:
    """Overwrite (in place) the fields the deterministic Title-17 table owns.

    Applied on EVERY zoning-cache read as well as at build time, so a correction
    to ``zoning_definitions.py`` takes effect immediately — the committed cache
    can never serve stale bulk numbers (``config_version`` fingerprints the
    extraction inputs, not the table). AI extraction keeps only the fields the
    table genuinely lacks: setbacks, parking, uses, special uses, notes.

    Field semantics (2026-07-06 audit):
    - far / max_height_ft: table-authoritative (AI mis-rowed ~7/59 zones).
    - lot_coverage_pct: force-None — NO Chicago base district has a Title-17
      lot-coverage standard; extraction tends to pick up rear-yard open-space
      percentages that are a different rule.
    - min_lot_area_sqft: table-authoritative (real for R districts only; B/C/M/D
      have no minimum lot size — the AI values were per-unit mis-rows).
    - min_lot_area_per_unit_sqft: deterministic dash-number/table rule.
    """
    from backend.retrieval.zoning_definitions import (
        get_zone_definition,
        min_lot_area_per_unit,
    )

    d = get_zone_definition(zone_class)
    # Fallback defs (PD/PMD/unknown) carry no standards — nothing authoritative.
    if d.is_fallback:
        return standards

    standards.far = d.far
    standards.max_height_ft = _height_ft_from_definition(d.max_height)
    standards.lot_coverage_pct = None
    standards.min_lot_area_sqft = d.min_lot_sqft
    standards.min_lot_area_per_unit_sqft = min_lot_area_per_unit(zone_class)
    # A district with no numeric cap (RM-6+, M, D) would otherwise just drop the
    # height row — surface the table's explanation instead. Guarded for
    # idempotence: the pass runs at build time AND on every read.
    if standards.max_height_ft is None and d.max_height:
        note = f"Height: {d.max_height}."
        if note not in standards.notes:
            standards.notes.append(note)
    return standards


def standards_from_definitions(zone_class: str) -> ZoningStandards | None:
    """Synthesize ZoningStandards from the deterministic Title 17 zone-class table.

    R1 fallback: when AI extraction is unavailable or low-confidence, the
    deterministic table (``zoning_definitions``) provides authoritative base-district
    FAR / height / density for known classes. Returns ``None`` for zones the
    table cannot resolve to real numbers (PD / PMD / unknown), so callers can preserve
    the raw-code-section path only for genuinely unknown districts.
    """
    from backend.retrieval.zoning_definitions import get_zone_definition

    d = get_zone_definition(zone_class)

    # Fallback defs (PD/PMD/unknown) carry no FAR — nothing reliable to surface.
    if d.is_fallback and d.far is None:
        return None

    # Keep the use description intact as a single line rather than naively
    # comma-splitting (which mangles commercial-district sentences).
    permitted_uses = [d.uses.strip()] if d.uses and d.uses.strip() else []

    notes = [
        "Standards from the deterministic Title 17 zone-class reference table "
        "(base district only), not site-specific code extraction. Overlays, planned "
        "developments, and transition zones may alter these. Verify with the City of "
        "Chicago Zoning Division.",
    ]
    if d.notes:
        notes.insert(0, d.notes)

    standards = ZoningStandards(
        permitted_uses=permitted_uses,
        notes=notes,
        extraction_confidence="definitions",
    )
    # Same authority pass the cache path uses — one source for the bulk numbers.
    return apply_table_authority(standards, zone_class)

EXTRACTION_SYSTEM = """You are a zoning code extraction specialist for Chicago's Municipal Code (Title 17).
Given retrieved text chunks from the zoning ordinance, extract structured development standards for the specified zone class.

Rules:
- Only extract values explicitly stated for the given zone class in the provided text.
- If a value is not found or ambiguous, output null for that field.
- For permitted_uses and special_uses, list broad category names (e.g. "Residential", "Retail Sales"), not individual business types.
- For parking fields, include the ratio (e.g. "1 per unit", "1 per 500 sq ft GFA").
- Set extraction_confidence based on how well the chunks match the target zone class:
  - "high": 3+ chunks directly reference bulk/density standards for this exact zone class
  - "medium": 1-2 chunks reference standards for this zone class, or standards for the zone category
  - "low": No chunks directly reference this zone class's standards (only general or adjacent classes)

Respond with ONLY a JSON object matching this schema:
{
  "far": float or null,
  "max_height_ft": int or null,
  "max_stories": int or null,
  "lot_coverage_pct": float or null,
  "min_lot_area_sqft": int or null,
  "front_setback_ft": int or null,
  "side_setback_ft": int or null,
  "rear_setback_ft": int or null,
  "parking_residential": "string or null",
  "parking_commercial": "string or null",
  "permitted_uses": ["category1", "category2"],
  "special_uses": ["category1"],
  "notes": ["important caveats"],
  "extraction_confidence": "high" | "medium" | "low"
}"""


def _json_from_model_text(text: str) -> str:
    """Return bare JSON from a model response that may be ```json-fenced or wrapped
    in prose.

    Haiku commonly fences its JSON (```json … ```); a naive ``json.loads`` then
    fails at char 0 — the historical reason every zoning extraction silently fell
    back to the deterministic Title-17 table instead of using the AI values.
    """
    t = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", t, re.DOTALL)
    if fence:
        return fence.group(1).strip()
    if not t.startswith("{"):
        obj = re.search(r"\{.*\}", t, re.DOTALL)
        if obj:
            return obj.group(0)
    return t


# Templated zoning queries — `zone_class` is the only variable. Module-level so the
# precompute builder and the cache's config_version hash both reference the exact
# same query shapes (a change here must invalidate the precomputed cache).
ZONING_QUERY_TEMPLATES = [
    "{zone_class} floor area ratio maximum building height lot coverage minimum lot area",
    "{zone_class} required setbacks front yard side yard rear yard transition setback",
    "{zone_class} permitted uses use group special use",
    "off-street parking spaces required {zone_class} dwelling unit commercial retail",
    "{zone_class} landscaping screening loading dock building entrance development standards",
]
ZONING_QUERY_LABELS = ["BULK STANDARDS", "SETBACKS", "USES", "PARKING", "DEVELOPMENT STANDARDS"]


async def extract_zoning_standards_with_provenance(
    zone_class: str,
    *,
    request_group: str = "report",
) -> tuple[ZoningStandards | None, list[str]]:
    """Run the 5 targeted vector searches + Haiku extraction for a zone class.

    Returns ``(standards, section_ids)`` where ``section_ids`` are the Municipal
    Code sections whose chunks fed the extraction — provenance for the precomputed
    zoning cache's staleness tracking. ``standards`` is ``None`` on any failure.

    Legacy semantic-search path; superseded by ``extract_zoning_standards_from_sections``
    for the builder. Kept for reference/tests. The live report reads the cache.
    """
    queries = [t.format(zone_class=zone_class) for t in ZONING_QUERY_TEMPLATES]

    try:
        chunk_groups = await asyncio.gather(
            *[semantic_search(q, top_k=3) for q in queries],
            return_exceptions=True,
        )
    except Exception as exc:
        log.warning("Vector search failed for zone %s: %s", zone_class, exc)
        return None, []

    # Build extraction text + collect contributing section IDs (provenance).
    sections: list[str] = []
    section_ids: list[str] = []
    for label, result in zip(ZONING_QUERY_LABELS, chunk_groups):
        if isinstance(result, Exception):
            continue
        for chunk in result:
            sections.append(f"[{label} — {chunk.section_title}]\n{chunk.text}")
            if chunk.section:
                section_ids.append(chunk.section)

    if not sections:
        log.warning("No vector search results for zone %s", zone_class)
        return None, []

    standards = await _haiku_extract(zone_class, "\n\n---\n\n".join(sections), request_group)
    return standards, sorted(set(section_ids))


# --- Deterministic full-section extraction (used by the offline cache builder) ---

# Title-17 "Bulk and density standards" section per district chapter (FAR, height,
# lot coverage, setbacks, min lot area). The per-zone numbers live in big tables
# that semantic search only partially retrieves, so the builder feeds the COMPLETE
# section instead. Residential is at -0300; the other chapters use -0400. (Verified
# 2026-06-18: flips B3-2/DX-7/M1-2 from low/null to high-confidence correct FAR.)
BULK_SECTION_BY_PREFIX = {
    "RS": "17-2-0300", "RT": "17-2-0300", "RM": "17-2-0300",
    "B": "17-3-0400", "C": "17-3-0400",
    "DX": "17-4-0400", "DC": "17-4-0400", "DR": "17-4-0400", "DS": "17-4-0400",
    "M": "17-5-0400",
}
SHARED_PARKING_SECTION = "17-10-0200"  # off-street parking ratios (all districts)


def _bulk_section_for(zone_class: str) -> str | None:
    m = re.match(r"[A-Z]+", (zone_class or "").strip().upper())
    return BULK_SECTION_BY_PREFIX.get(m.group(0)) if m else None


async def extract_zoning_standards_from_sections(
    zone_class: str,
    *,
    request_group: str = "report",
    include_parking: bool = True,
) -> tuple[ZoningStandards | None, list[str]]:
    """Deterministic extraction: feed the FULL Title-17 bulk (+ parking) sections.

    Fetches the complete bulk-and-density table for the zone's district chapter
    (and the shared parking ratios) via ``get_full_section`` so the extractor sees
    the zone's actual numeric row instead of a partial semantic-search chunk. No
    reranker, no fuzzy ranking. Used by the offline cache builder.
    """
    bulk_id = _bulk_section_for(zone_class)
    if not bulk_id:
        return None, []  # PD/PMD/POS/T etc. — no chapter bulk table; table fallback handles these
    section_ids = [bulk_id] + ([SHARED_PARKING_SECTION] if include_parking else [])

    chunks = await asyncio.gather(*[get_full_section(s) for s in section_ids])
    parts, used = [], []
    for sid, chunk in zip(section_ids, chunks):
        if chunk and chunk.text:
            parts.append(f"[{chunk.section} — {chunk.section_title}]\n{chunk.text}")
            used.append(sid)
    if not parts:
        log.warning("No full sections fetched for zone %s (%s)", zone_class, section_ids)
        return None, []

    standards = await _haiku_extract(zone_class, "\n\n---\n\n".join(parts), request_group)
    return standards, used


async def _haiku_extract(
    zone_class: str, extraction_text: str, request_group: str
) -> ZoningStandards | None:
    """Run Haiku JSON extraction over already-assembled retrieved text."""
    settings = get_settings()
    try:
        resp = await tracked_create(
            request_group=request_group,
            conversation_id=None,
            phase="zoning_extraction",
            model=settings.zoning_extract_model,
            max_tokens=settings.zoning_extract_max_tokens,
            system=EXTRACTION_SYSTEM,
            messages=[{
                "role": "user",
                "content": f"Zone class: {zone_class}\n\nRetrieved text:\n\n{extraction_text}",
            }],
        )
    except Exception as exc:
        log.warning("Haiku extraction failed for zone %s: %s", zone_class, exc)
        return None

    text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
    try:
        return ZoningStandards(**json.loads(_json_from_model_text(text)))
    except (json.JSONDecodeError, Exception) as exc:
        log.warning("Failed to parse extraction JSON for zone %s: %s", zone_class, exc)
        return None


async def extract_zoning_standards(
    zone_class: str,
    *,
    request_group: str = "report",
) -> ZoningStandards | None:
    """Run 5 targeted vector searches and extract structured standards via Haiku."""
    standards, _ = await extract_zoning_standards_with_provenance(
        zone_class, request_group=request_group
    )
    return standards


def calculate_development_potential(
    standards: ZoningStandards,
    land_sqft: int,
    bldg_sqft: int,
) -> DevelopmentPotential:
    """Calculate development potential from extracted zoning standards."""
    max_buildable: int | None = None
    max_coverage: int | None = None
    surplus: int | None = None
    parking_est: int | None = None

    if standards.far is not None and land_sqft > 0:
        max_buildable = int(standards.far * land_sqft)
        surplus = max_buildable - bldg_sqft

    if standards.lot_coverage_pct is not None and land_sqft > 0:
        max_coverage = int(standards.lot_coverage_pct * land_sqft)

    return DevelopmentPotential(
        max_buildable_sqft=max_buildable,
        max_lot_coverage_sqft=max_coverage,
        development_surplus_sqft=surplus,
        parking_spaces_estimated=parking_est,
    )
