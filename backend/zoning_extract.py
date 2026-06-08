"""Extract structured zoning standards from Municipal Code via Haiku.

Runs 5 targeted vector searches for a given zone class, then uses Claude Haiku
to extract structured parameters (FAR, height, setbacks, uses, parking) into
a ZoningStandards model.
"""

import asyncio
import json
import logging
from typing import Any

from backend.config import get_settings
from backend.llm import tracked_create
from backend.models import DevelopmentPotential, ZoningStandards
from backend.retrieval.vector_search import semantic_search

log = logging.getLogger(__name__)

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


async def extract_zoning_standards(
    zone_class: str,
    *,
    request_group: str = "report",
) -> ZoningStandards | None:
    """Run 5 targeted vector searches and extract structured standards via Haiku."""
    settings = get_settings()

    queries = [
        f"{zone_class} floor area ratio maximum building height lot coverage minimum lot area",
        f"{zone_class} required setbacks front yard side yard rear yard transition setback",
        f"{zone_class} permitted uses use group special use",
        f"off-street parking spaces required {zone_class} dwelling unit commercial retail",
        f"{zone_class} landscaping screening loading dock building entrance development standards",
    ]
    labels = ["BULK STANDARDS", "SETBACKS", "USES", "PARKING", "DEVELOPMENT STANDARDS"]

    try:
        chunk_groups = await asyncio.gather(
            *[semantic_search(q, top_k=3) for q in queries],
            return_exceptions=True,
        )
    except Exception as exc:
        log.warning("Vector search failed for zone %s: %s", zone_class, exc)
        return None

    # Build extraction text from all successful searches
    sections: list[str] = []
    for label, result in zip(labels, chunk_groups):
        if isinstance(result, Exception):
            continue
        for chunk in result:
            sections.append(f"[{label} — {chunk.section_title}]\n{chunk.text}")

    if not sections:
        log.warning("No vector search results for zone %s", zone_class)
        return None

    extraction_text = "\n\n---\n\n".join(sections)

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
                "content": (
                    f"Zone class: {zone_class}\n\n"
                    f"Retrieved text:\n\n{extraction_text}"
                ),
            }],
        )
    except Exception as exc:
        log.warning("Haiku extraction failed for zone %s: %s", zone_class, exc)
        return None

    text = "".join(
        b.text for b in resp.content if getattr(b, "type", "") == "text"
    )

    try:
        data = json.loads(text)
        return ZoningStandards(**data)
    except (json.JSONDecodeError, Exception) as exc:
        log.warning("Failed to parse extraction JSON for zone %s: %s", zone_class, exc)
        return None


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
