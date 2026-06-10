"""Deterministic zoning district definitions sourced from Chicago Municipal Code Title 17.

Every value in this module is traceable to a specific section of Title 17. Values change
only when the ordinance is amended. This is NOT a probabilistic retrieval layer — it is
a structured reference table for known, published zoning standards.

Source sections:
  - Residential districts: Title 17, Chapter 17-2 (§17-2-0100 descriptions, §17-2-0300 bulk)
  - Business/Commercial districts: Title 17, Chapter 17-3 (§17-3-0100, §17-3-0400 bulk)
  - Downtown districts: Title 17, Chapter 17-4 (§17-4-0100, §17-4-0400 bulk)
  - Manufacturing districts: Title 17, Chapter 17-5 (§17-5-0100, §17-5-0400 bulk)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass(frozen=True)
class ZoneDefinition:
    zone_class: str
    name: str
    code_section: str
    far: float | None = None
    max_height: str | None = None
    lot_coverage: str | None = None
    uses: str = ""
    notes: str = ""
    is_fallback: bool = field(default=False, repr=False)


# ---------------------------------------------------------------------------
# Zone category names (prefix → human-readable name)
# ---------------------------------------------------------------------------

ZONE_NAMES: dict[str, str] = {
    "RS": "Residential Single-Unit (Detached House)",
    "RT": "Residential Two-Flat, Townhouse & Multi-Unit",
    "RM": "Residential Multi-Unit",
    "B1": "Neighborhood Shopping",
    "B2": "Neighborhood Mixed-Use",
    "B3": "Community Shopping",
    "C1": "Neighborhood Commercial",
    "C2": "Motor Vehicle-Related Commercial",
    "C3": "Commercial, Manufacturing & Employment",
    "M1": "Limited Manufacturing / Business Park",
    "M2": "Light Industry",
    "M3": "Heavy Industry",
    "DX": "Downtown Mixed-Use",
    "DC": "Downtown Core",
    "DR": "Downtown Residential",
    "DS": "Downtown Service",
    "POS": "Parks & Open Space",
    "PMD": "Planned Manufacturing District",
    "PD": "Planned Development",
    "T": "Transportation",
}


# ---------------------------------------------------------------------------
# Full zone class data — every standard Chicago zone class
# ---------------------------------------------------------------------------

_RES_USES = "Detached houses, two-flats, townhouses, parks, schools, religious institutions, home occupations"
_RS_USES = "Detached houses, parks, schools, religious institutions, home occupations"
_RM_USES = "Detached houses, two-flats, townhouses, multi-unit buildings, parks, schools, community centers"
_B1_USES = "Small-scale retail, restaurants, personal services, offices; residential above ground floor. All operations indoors."
_B2_USES = "Retail, restaurants, services, offices; residential on or above ground floor. All operations indoors."
_B3_USES = "Broad retail, restaurants, services, entertainment, offices; residential above ground floor. Destination-oriented, higher parking."
_C1_USES = "Retail, restaurants, offices, personal services, auto-oriented commercial; residential above ground floor."
_C2_USES = "Broadest commercial: nearly any business/service/commercial use including outdoor operations and storage; residential above ground floor."
_C3_USES = "Commercial and light manufacturing mix; warehousing, distribution, offices, retail. Outdoor operations permitted."
_M1_USES = "Light manufacturing, offices, business parks, warehousing. No residential."
_M2_USES = "Moderate manufacturing, warehousing, distribution. Limited retail. No residential."
_M3_USES = "Heavy manufacturing, processing, warehousing. Most intensive industrial uses. No residential."
_DX_USES = "Mixed-use: offices, retail, hotels, entertainment, residential. High-density urban core."
_DC_USES = "Highest-density core: offices, retail, hotels, entertainment, residential."
_DR_USES = "High-density residential with limited ground-floor commercial."
_DS_USES = "Service and support uses for downtown: parking, utilities, warehousing, offices."

ZONE_CLASS_DATA: dict[str, ZoneDefinition] = {
    # --- Residential Single-Unit (§17-2-0102, §17-2-0300) ---
    "RS-1": ZoneDefinition("RS-1", "Residential Single-Unit", "§17-2-0102", far=0.50, max_height="30 ft", lot_coverage="50%", uses=_RS_USES, notes="Largest lot size. Detached houses only."),
    "RS-2": ZoneDefinition("RS-2", "Residential Single-Unit", "§17-2-0102", far=0.65, max_height="30 ft", lot_coverage="50%", uses=_RS_USES, notes="Standard single-family. Detached houses only."),
    "RS-3": ZoneDefinition("RS-3", "Residential Single-Unit", "§17-2-0102", far=0.90, max_height="30 ft", lot_coverage="55%", uses=_RS_USES, notes="Most common RS district. Smaller lots."),

    # --- Residential Two-Flat/Townhouse (§17-2-0103, §17-2-0300) ---
    "RT-3.5": ZoneDefinition("RT-3.5", "Residential Two-Flat, Townhouse & Multi-Unit", "§17-2-0103", far=1.05, max_height="35 ft", lot_coverage="55%", uses=_RES_USES),
    "RT-4": ZoneDefinition("RT-4", "Residential Two-Flat, Townhouse & Multi-Unit", "§17-2-0103", far=1.20, max_height="38 ft", lot_coverage="60%", uses=_RES_USES),

    # --- Residential Multi-Unit (§17-2-0104, §17-2-0300) ---
    "RM-4.5": ZoneDefinition("RM-4.5", "Residential Multi-Unit", "§17-2-0104", far=1.70, max_height="38 ft", lot_coverage="60%", uses=_RM_USES, notes="Transition district between RT-4 and RM-5."),
    "RM-5": ZoneDefinition("RM-5", "Residential Multi-Unit", "§17-2-0104", far=2.00, max_height="45 ft", lot_coverage="60%", uses=_RM_USES, notes="Moderate-density multi-unit."),
    "RM-5.5": ZoneDefinition("RM-5.5", "Residential Multi-Unit", "§17-2-0104", far=2.50, max_height="50 ft", lot_coverage="60%", uses=_RM_USES),
    "RM-6": ZoneDefinition("RM-6", "Residential Multi-Unit", "§17-2-0104", far=4.40, max_height="70 ft", lot_coverage="60%", uses=_RM_USES, notes="High-density. FAR premium may apply (§17-2-0304)."),
    "RM-6.5": ZoneDefinition("RM-6.5", "Residential Multi-Unit", "§17-2-0104", far=6.60, max_height="90 ft", lot_coverage="60%", uses=_RM_USES, notes="Highest-density residential."),

    # --- Business: B1 Neighborhood Shopping (§17-3-0102, §17-3-0400) ---
    "B1-1": ZoneDefinition("B1-1", "Neighborhood Shopping", "§17-3-0102", far=1.2, max_height="38 ft (varies by lot frontage)", uses=_B1_USES),
    "B1-1.5": ZoneDefinition("B1-1.5", "Neighborhood Shopping", "§17-3-0102", far=1.5, max_height="38 ft (varies by lot frontage)", uses=_B1_USES),
    "B1-2": ZoneDefinition("B1-2", "Neighborhood Shopping", "§17-3-0102", far=2.2, max_height="50 ft (varies by lot frontage)", uses=_B1_USES),
    "B1-3": ZoneDefinition("B1-3", "Neighborhood Shopping", "§17-3-0102", far=3.0, max_height="65 ft (varies by lot frontage)", uses=_B1_USES),
    "B1-5": ZoneDefinition("B1-5", "Neighborhood Shopping", "§17-3-0102", far=5.0, max_height="80 ft (varies by lot frontage)", uses=_B1_USES),

    # --- Business: B2 Neighborhood Mixed-Use (§17-3-0103, §17-3-0400) ---
    "B2-1": ZoneDefinition("B2-1", "Neighborhood Mixed-Use", "§17-3-0103", far=1.2, max_height="38 ft (varies by lot frontage)", uses=_B2_USES),
    "B2-2": ZoneDefinition("B2-2", "Neighborhood Mixed-Use", "§17-3-0103", far=2.2, max_height="50 ft (varies by lot frontage)", uses=_B2_USES, notes="Residential permitted on or above ground floor."),
    "B2-3": ZoneDefinition("B2-3", "Neighborhood Mixed-Use", "§17-3-0103", far=3.0, max_height="65 ft (varies by lot frontage)", uses=_B2_USES),
    "B2-5": ZoneDefinition("B2-5", "Neighborhood Mixed-Use", "§17-3-0103", far=5.0, max_height="80 ft (varies by lot frontage)", uses=_B2_USES),

    # --- Business: B3 Community Shopping (§17-3-0104, §17-3-0400) ---
    "B3-1": ZoneDefinition("B3-1", "Community Shopping", "§17-3-0104", far=1.2, max_height="38 ft (varies by lot frontage)", uses=_B3_USES),
    "B3-1.5": ZoneDefinition("B3-1.5", "Community Shopping", "§17-3-0104", far=1.5, max_height="38 ft (varies by lot frontage)", uses=_B3_USES),
    "B3-2": ZoneDefinition("B3-2", "Community Shopping", "§17-3-0104", far=2.2, max_height="50 ft (varies by lot frontage)", uses=_B3_USES),
    "B3-3": ZoneDefinition("B3-3", "Community Shopping", "§17-3-0104", far=3.0, max_height="65 ft (varies by lot frontage)", uses=_B3_USES),
    "B3-5": ZoneDefinition("B3-5", "Community Shopping", "§17-3-0104", far=5.0, max_height="80 ft (varies by lot frontage)", uses=_B3_USES),

    # --- Commercial: C1 Neighborhood Commercial (§17-3-0105, §17-3-0400) ---
    "C1-1": ZoneDefinition("C1-1", "Neighborhood Commercial", "§17-3-0105", far=1.2, max_height="38 ft (varies by lot frontage)", uses=_C1_USES),
    "C1-1.5": ZoneDefinition("C1-1.5", "Neighborhood Commercial", "§17-3-0105", far=1.5, max_height="38 ft (varies by lot frontage)", uses=_C1_USES),
    "C1-2": ZoneDefinition("C1-2", "Neighborhood Commercial", "§17-3-0105", far=2.2, max_height="50 ft (varies by lot frontage)", uses=_C1_USES),
    "C1-3": ZoneDefinition("C1-3", "Neighborhood Commercial", "§17-3-0105", far=3.0, max_height="65 ft (varies by lot frontage)", uses=_C1_USES),
    "C1-5": ZoneDefinition("C1-5", "Neighborhood Commercial", "§17-3-0105", far=5.0, max_height="80 ft (varies by lot frontage)", uses=_C1_USES),

    # --- Commercial: C2 Motor Vehicle-Related (§17-3-0106, §17-3-0400) ---
    "C2-1": ZoneDefinition("C2-1", "Motor Vehicle-Related Commercial", "§17-3-0106", far=1.2, max_height="38 ft (varies by lot frontage)", uses=_C2_USES),
    "C2-2": ZoneDefinition("C2-2", "Motor Vehicle-Related Commercial", "§17-3-0106", far=2.2, max_height="50 ft (varies by lot frontage)", uses=_C2_USES),
    "C2-3": ZoneDefinition("C2-3", "Motor Vehicle-Related Commercial", "§17-3-0106", far=3.0, max_height="65 ft (varies by lot frontage)", uses=_C2_USES),
    "C2-5": ZoneDefinition("C2-5", "Motor Vehicle-Related Commercial", "§17-3-0106", far=5.0, max_height="80 ft (varies by lot frontage)", uses=_C2_USES),

    # --- Commercial: C3 Commercial/Manufacturing (§17-3-0107, §17-3-0400) ---
    "C3-1": ZoneDefinition("C3-1", "Commercial, Manufacturing & Employment", "§17-3-0107", far=1.2, max_height="38 ft (varies by lot frontage)", uses=_C3_USES),
    "C3-2": ZoneDefinition("C3-2", "Commercial, Manufacturing & Employment", "§17-3-0107", far=2.2, max_height="50 ft (varies by lot frontage)", uses=_C3_USES),
    "C3-3": ZoneDefinition("C3-3", "Commercial, Manufacturing & Employment", "§17-3-0107", far=3.0, max_height="65 ft (varies by lot frontage)", uses=_C3_USES),
    "C3-5": ZoneDefinition("C3-5", "Commercial, Manufacturing & Employment", "§17-3-0107", far=5.0, max_height="80 ft (varies by lot frontage)", uses=_C3_USES),

    # --- Manufacturing: M1 Limited (§17-5-0102, §17-5-0400) ---
    "M1-1": ZoneDefinition("M1-1", "Limited Manufacturing / Business Park", "§17-5-0102", far=1.2, max_height="38 ft", uses=_M1_USES),
    "M1-2": ZoneDefinition("M1-2", "Limited Manufacturing / Business Park", "§17-5-0102", far=2.2, max_height="50 ft", uses=_M1_USES),
    "M1-3": ZoneDefinition("M1-3", "Limited Manufacturing / Business Park", "§17-5-0102", far=3.0, max_height="65 ft", uses=_M1_USES),

    # --- Manufacturing: M2 Light Industry (§17-5-0103, §17-5-0400) ---
    "M2-1": ZoneDefinition("M2-1", "Light Industry", "§17-5-0103", far=1.2, max_height="38 ft", uses=_M2_USES),
    "M2-2": ZoneDefinition("M2-2", "Light Industry", "§17-5-0103", far=2.2, max_height="50 ft", uses=_M2_USES),
    "M2-3": ZoneDefinition("M2-3", "Light Industry", "§17-5-0103", far=3.0, max_height="65 ft", uses=_M2_USES),

    # --- Manufacturing: M3 Heavy Industry (§17-5-0104, §17-5-0400) ---
    "M3-1": ZoneDefinition("M3-1", "Heavy Industry", "§17-5-0104", far=1.2, max_height="38 ft", uses=_M3_USES),
    "M3-2": ZoneDefinition("M3-2", "Heavy Industry", "§17-5-0104", far=2.2, max_height="50 ft", uses=_M3_USES),
    "M3-3": ZoneDefinition("M3-3", "Heavy Industry", "§17-5-0104", far=3.0, max_height="65 ft", uses=_M3_USES),

    # --- Downtown: DX Mixed-Use (§17-4-0102, §17-4-0400) ---
    "DX-3": ZoneDefinition("DX-3", "Downtown Mixed-Use", "§17-4-0102", far=3.0, max_height="No max (bonuses available)", uses=_DX_USES),
    "DX-5": ZoneDefinition("DX-5", "Downtown Mixed-Use", "§17-4-0102", far=5.0, max_height="No max (bonuses available)", uses=_DX_USES),
    "DX-7": ZoneDefinition("DX-7", "Downtown Mixed-Use", "§17-4-0102", far=7.0, max_height="No max (bonuses available)", uses=_DX_USES),
    "DX-12": ZoneDefinition("DX-12", "Downtown Mixed-Use", "§17-4-0102", far=12.0, max_height="No max (bonuses available)", uses=_DX_USES),
    "DX-16": ZoneDefinition("DX-16", "Downtown Mixed-Use", "§17-4-0102", far=16.0, max_height="No max (bonuses available)", uses=_DX_USES),

    # --- Downtown: DC Core (§17-4-0103, §17-4-0400) ---
    "DC-12": ZoneDefinition("DC-12", "Downtown Core", "§17-4-0103", far=12.0, max_height="No max (bonuses available)", uses=_DC_USES),
    "DC-16": ZoneDefinition("DC-16", "Downtown Core", "§17-4-0103", far=16.0, max_height="No max (bonuses available)", uses=_DC_USES),

    # --- Downtown: DR Residential (§17-4-0104, §17-4-0400) ---
    "DR-3": ZoneDefinition("DR-3", "Downtown Residential", "§17-4-0104", far=3.0, max_height="No max (bonuses available)", uses=_DR_USES),
    "DR-5": ZoneDefinition("DR-5", "Downtown Residential", "§17-4-0104", far=5.0, max_height="No max (bonuses available)", uses=_DR_USES),
    "DR-7": ZoneDefinition("DR-7", "Downtown Residential", "§17-4-0104", far=7.0, max_height="No max (bonuses available)", uses=_DR_USES),
    "DR-10": ZoneDefinition("DR-10", "Downtown Residential", "§17-4-0104", far=10.0, max_height="No max (bonuses available)", uses=_DR_USES),

    # --- Downtown: DS Service (§17-4-0105, §17-4-0400) ---
    "DS-3": ZoneDefinition("DS-3", "Downtown Service", "§17-4-0105", far=3.0, max_height="No max (bonuses available)", uses=_DS_USES),
    "DS-5": ZoneDefinition("DS-5", "Downtown Service", "§17-4-0105", far=5.0, max_height="No max (bonuses available)", uses=_DS_USES),

    # --- Special districts ---
    "POS-1": ZoneDefinition("POS-1", "Parks & Open Space", "§17-6-0200", uses="Parks, recreation, cultural facilities, forest preserves"),
    "POS-2": ZoneDefinition("POS-2", "Parks & Open Space (Cemeteries)", "§17-6-0200", uses="Cemeteries, memorial parks"),
}


# ---------------------------------------------------------------------------
# Lookup functions
# ---------------------------------------------------------------------------

def _parse_zone_prefix(zone_class: str) -> tuple[str, str | None]:
    """Parse a zone class into (sub-category prefix, dash number).

    Examples:
        "C1-2" → ("C1", "2")
        "RS-3" → ("RS", "3")
        "PD 799" → ("PD", "799")
        "B3-1.5" → ("B3", "1.5")
        "PMD 12" → ("PMD", "12")
    """
    s = zone_class.strip().upper()
    m = re.match(r"^([A-Z]+[\d]?\.?\d?)[\s-]*([\d.]+)?$", s)
    if m:
        return m.group(1), m.group(2)
    m2 = re.match(r"^([A-Z]+)", s)
    if m2:
        return m2.group(1), None
    return s, None


def get_zone_name(zone_class: str) -> str:
    """Return a one-line human-readable name for a zone class.

    Used as a Jinja filter for inline descriptions. Always returns a string —
    falls back to prefix name, then the raw zone code.
    """
    normalized = zone_class.strip().upper()
    exact = ZONE_CLASS_DATA.get(normalized)
    if exact:
        suffix = f" (FAR {exact.far})" if exact.far is not None else ""
        return f"{exact.name}{suffix}"

    prefix, _ = _parse_zone_prefix(zone_class)

    if prefix in ("PD", "PMD"):
        name = ZONE_NAMES.get(prefix, prefix)
        return f"{name} (site-specific standards)"

    if prefix in ZONE_NAMES:
        return ZONE_NAMES[prefix]

    broad = re.match(r"^([A-Z]+)", prefix)
    if broad and broad.group(1) in ZONE_NAMES:
        return ZONE_NAMES[broad.group(1)]

    return zone_class


def get_zone_definition(zone_class: str) -> ZoneDefinition:
    """Return a full ZoneDefinition for a zone class.

    Fallback chain:
    1. Exact match in ZONE_CLASS_DATA
    2. PD/PMD → generic planned development definition
    3. Prefix match → generic category definition
    4. Unknown → definition with raw code and advisory note
    """
    normalized = zone_class.strip().upper()
    exact = ZONE_CLASS_DATA.get(normalized)
    if exact:
        return exact

    prefix, dash = _parse_zone_prefix(zone_class)

    if prefix == "PD" or prefix == "PMD":
        name = ZONE_NAMES.get(prefix, "Planned Development")
        return ZoneDefinition(
            zone_class=normalized,
            name=name,
            code_section="§17-8-0500" if prefix == "PD" else "§17-6-0400",
            uses="Standards are site-specific per the approved planned development ordinance.",
            notes="Planned developments have individually negotiated standards approved by City Council. "
                  "Consult the specific PD ordinance for FAR, height, use, and setback requirements.",
            is_fallback=True,
        )

    for candidate_prefix in (prefix, re.match(r"^([A-Z]+)", prefix).group(1) if re.match(r"^([A-Z]+)", prefix) else prefix):
        if candidate_prefix in ZONE_NAMES:
            return ZoneDefinition(
                zone_class=normalized,
                name=ZONE_NAMES[candidate_prefix],
                code_section="Title 17",
                uses=f"See Title 17 for uses permitted in {candidate_prefix} districts.",
                notes=f"Non-standard designation. Verify standards with the City of Chicago Zoning Division.",
                is_fallback=True,
            )

    return ZoneDefinition(
        zone_class=normalized,
        name=normalized,
        code_section="Title 17",
        notes="Zone class not recognized. Verify with the City of Chicago Zoning Division.",
        is_fallback=True,
    )


def collect_report_zone_definitions(
    subject_zone: str | None,
    adjacent_zones: dict[str, str | None] | None,
) -> list[ZoneDefinition]:
    """Collect definitions for all unique zone classes in a report.

    Returns definitions sorted with the subject zone first, then adjacent
    zones alphabetically by zone class.
    """
    zones: dict[str, ZoneDefinition] = {}

    if subject_zone:
        zones[subject_zone.strip().upper()] = get_zone_definition(subject_zone)

    if adjacent_zones:
        for zone in adjacent_zones.values():
            if zone:
                norm = zone.strip().upper()
                if norm not in zones:
                    zones[norm] = get_zone_definition(zone)

    if not zones:
        return []

    result: list[ZoneDefinition] = []
    if subject_zone:
        subj_norm = subject_zone.strip().upper()
        if subj_norm in zones:
            result.append(zones.pop(subj_norm))

    result.extend(sorted(zones.values(), key=lambda d: d.zone_class))
    return result
