"""Where each Property Profile fact came from, and how current that is.

A fact a reader could act on carries a dated source: the official record it was read
from (layer, ordinance, feature), or the code section it is computed from, with the
date the source says it is current and the date we queried it. This is the data
behind "click a number, see the source" (V2); it makes a claim checkable instead of
asking to be trusted.

Every entry is a plain dict (JSON-safe), keyed by a stable fact id:

    zoning.district                    the district + the ordinance that set it
    zoning.far / .max_height /
      .min_lot_area_per_unit           the standard + the code section it comes from
    overlay.<layer_type>               each overlay found + the layer it came from
    parcel.identity                    which parcel, and how it was identified
    property.land_sqft / .bldg_sqft    the area figure + which dataset supplied it
    code.vintage                       how current the indexed Municipal Code is

Fields: ``label`` (plain words), ``kind`` (official_record | code_text | derived),
``source`` (the dataset or code), ``record_id``, ``url``, ``section`` (a code section
id the source viewer can open), ``as_of`` (when the source says its record last
changed / the code is current through), ``effective_date`` (when the rule took
effect, e.g. the ordinance date) and ``query_date`` (when we asked). Any may be None;
an entry always carries a ``query_date``.

Schema v2 (WS0 M2, see ``claude-context/guides/source-confidence.md``) adds, all additive:
``tier`` / ``source_id`` (who published it), ``as_of_basis`` / ``age_days`` (what the date
means), ``scope`` / ``geography`` / ``coverage`` (how much it covers), ``precision``,
``method_key`` / ``method`` (how it was made), ``value`` (the figure as displayed) and the
derived ``confidence`` / ``confidence_reasons``. ``kind`` stays one release as an alias of
``tier``. Entries are built through :func:`make_entry`; the confidence state is computed
once, in :func:`confidence_state`, and every surface reads it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from backend.code_vintage import get_code_vintage
from backend.retrieval.regulatory.overlays import OVERLAY_LAYERS
from backend.retrieval.zoning_definitions import _parse_zone_prefix

ZONING_LAYER = "City of Chicago Zoning Districts, Zoning MapServer layer 1"
CODE_SOURCE = "Municipal Code of Chicago, Title 17 (Zoning Ordinance)"

# Code sections each standard comes from, by district family. Pinned to the ingested
# code's section headings in tests/test_provenance.py. None = the code sets no such
# standard for the family (M districts have no height or per-unit standard).
BULK_SECTIONS: dict[str, dict[str, str | None]] = {
    "R": {"far": "17-2-0304-A", "max_height": "17-2-0311-A", "min_lot_area_per_unit": "17-2-0303-A"},
    "BC": {"far": "17-3-0403-A", "max_height": "17-3-0408-A", "min_lot_area_per_unit": "17-3-0402-A"},
    "M": {"far": "17-5-0404", "max_height": None, "min_lot_area_per_unit": None},
    "D": {"far": "17-4-0405-A", "max_height": "17-4-0407", "min_lot_area_per_unit": "17-4-0404-A"},
}

_BULK_LABELS = {
    "far": "Floor area ratio",
    "max_height": "Maximum building height",
    "min_lot_area_per_unit": "Minimum lot area per dwelling unit",
}

_LAYER_ID_BY_TYPE = {meta["type"]: lid for lid, meta in OVERLAY_LAYERS.items()}

_AREA_SOURCES = {
    "assessor": "Cook County Assessor (parcel characteristics)",
    "gis": "Cook County GIS parcel layer",
    "geometry": "Parcel polygon area (Cook County property-tax database)",
    "condo_unit": "Cook County Assessor condominium characteristics (one unit's area)",
    "commercial_valuation": "Cook County Assessor commercial valuation (economic-unit total)",
    "footprint": "City of Chicago building footprints (ground-floor area)",
    "energy_benchmark": "City of Chicago energy benchmarking (owner-reported gross floor area)",
}


def bulk_family(zone_class: str | None) -> str | None:
    """'R', 'BC', 'M', 'D' for the districts that have bulk tables; None for PD/POS/unknown."""
    if not zone_class:
        return None
    prefix, _ = _parse_zone_prefix(zone_class.strip().upper())
    if prefix in ("RS", "RT", "RM"):
        return "R"
    if prefix in ("B1", "B2", "B3", "C1", "C2", "C3"):
        return "BC"
    if prefix in ("M1", "M2", "M3"):
        return "M"
    if prefix in ("DX", "DC", "DR", "DS"):
        return "D"
    return None


# --- schema v2 -----------------------------------------------------------------------------------

Tier = Literal[
    "official_record", "official_publication", "official_estimate",
    "our_calculation", "ai_extracted", "non_government",
]
MethodKey = Literal[
    "recorded", "published_text", "code_table", "hand_reviewed",
    "survey_estimate", "government_model", "bracket_median", "calculation", "keyword_grouping",
    "ai_read_code", "ai_read_ordinance", "ai_read_filing",
    "commercial_index",
]
# ``record_updated`` is the one addition to the guide's list: the date one record last changed
# (a zoning district's map edit). It says nothing about how current the dataset is, so it
# never triggers the 24-month ``old_source`` rule that ``source_updated`` does.
AsOfBasis = Literal[
    "source_updated", "record_updated", "current_through", "period_end", "vintage", "tax_year", "queried",
]
Scope = Literal["parcel", "address", "radius", "tract", "community_area", "city", "county"]
Confidence = Literal["standard", "low", "withheld"]
# What kind of n a coverage figure counts, which decides which n rule applies (guide §3):
# ``area_sample`` = a median/rate from a sample of records; ``comps`` = a comparable-sales set.
# None = a list where every record is shown, or a share with no sample-size rule.
SampleKind = Literal["area_sample", "comps"]

# Strongest to weakest, by the guide's letters A-F. A calculation is never read as stronger
# than its weakest input.
TIER_ORDER: tuple[str, ...] = (
    "official_record", "official_publication", "official_estimate",
    "our_calculation", "ai_extracted", "non_government",
)
_KIND_BY_TIER = {"official_record": "official_record", "official_publication": "code_text"}

# Thresholds (guide §3). Boundary tests pin them: a value exactly at a constant is not past it.
HIDE_COVERAGE_BELOW = 0.10
FADE_COVERAGE_BELOW = 0.25
FADE_CV_ABOVE = 0.30
HIDE_CV_ABOVE = 0.50
HIDE_N_BELOW = 30
COMPS_FADE_N_BELOW = 5
COMPS_HIDE_N_BELOW = 3
AI_CORROBORATED_RATE = 0.95
AI_CORROBORATED_MIN_N = 30
OLD_SOURCE_DAYS = 730  # "more than 24 months" (guide §4.1)
_OLD_SOURCE_BASES = ("source_updated", "vintage", "period_end", "tax_year")

METHOD_TEXT: dict[str, str] = {
    "recorded": "Read as recorded by the publisher",
    "published_text": "Quoted from the published Municipal Code",
    "code_table": "Our Title 17 table, checked against the code text",
    "hand_reviewed": "An ordinance passed but not yet in the published code, read by us",
    "survey_estimate": "Census survey estimate",
    "government_model": "A government agency's model",
    "bracket_median": "Median interpolated from published brackets",
    "calculation": "Our calculation",
    "keyword_grouping": "Our grouping of free text into categories",
    "ai_read_code": "Read by AI from Municipal Code text",
    "ai_read_ordinance": "Read by AI from a scanned ordinance",
    "ai_read_filing": "Read by AI from the applicant's filing",
    "commercial_index": "A private company's index",
}


class Coverage(BaseModel):
    """How much of a universe a figure rests on. ``None`` on a parcel record means "not applicable"."""

    n: int | None = None
    share: float | None = None
    universe: str | None = None
    unit: str | None = None
    sample: SampleKind | None = None


class Agreement(BaseModel):
    n: int
    agree: int


class Precision(BaseModel):
    """Published error (``moe`` at ``moe_level``, ``cv``) or, for an AI reading, a measured agreement rate."""

    moe: float | None = None
    moe_level: float | None = None
    cv: float | None = None
    agreement: Agreement | None = None


class ProvenanceEntry(BaseModel):
    """One fact's source, date, coverage, precision and method. Dumps to the dict the wire carries."""

    model_config = ConfigDict(extra="forbid")

    # v1 fields (unchanged meaning)
    label: str
    kind: Literal["official_record", "code_text", "derived"]
    source: str | None = None
    record_id: str | None = None
    url: str | None = None
    section: str | None = None
    as_of: str | None = None
    effective_date: str | None = None
    query_date: str
    note: str | None = None
    # 1. who published it
    tier: Tier
    source_id: str | None = None
    # 2. how old
    as_of_basis: AsOfBasis
    period: str | None = None
    age_days: int | None = None
    # 3. how much it covers
    scope: Scope | None = None
    geography: str | None = None
    coverage: Coverage | None = None
    # 4. how precise
    precision: Precision | None = None
    # 5. how made
    method_key: MethodKey
    method_params: dict[str, Any] | None = None
    method: str
    # calculations: what they rest on, and the weakest of it
    inputs: list[str] | None = None
    basis_tier: Tier | None = None
    # AI readings: a deterministic check agreed (guide §3)
    corroborated: bool | None = None
    # derived, set once by make_entry
    confidence: Confidence = "standard"
    confidence_reasons: list[str] = Field(default_factory=list)
    value: str | int | float | bool | None = None

    def to_dict(self) -> dict:
        """The wire dict. The v1 keys are always present (``note`` too: v1 carried it as null);
        v2 extras only when set."""
        d = self.model_dump(mode="json")
        always = {*_V1_KEYS, "tier", "as_of_basis", "method_key", "method", "confidence", "confidence_reasons"}
        return {k: v for k, v in d.items() if k in always or (v is not None and v != [])}


_V1_KEYS = ("label", "kind", "source", "record_id", "url", "section", "as_of", "effective_date", "query_date", "note")


@dataclass(frozen=True)
class FactSpec:
    """A figure's static identity. Per-source facts (publisher, tier, vintage) live in the
    data-health registry, read by ``source_id``; a spec only names the source."""

    label: str
    source_id: str
    method_key: str
    scope: str
    tier: str
    # other sources that can supply the same recorded figure (lot/building area, parcel identity)
    alt_source_ids: tuple[str, ...] = ()
    # sources the figure is computed or located from in some variants (a polygon area, the nearest
    # parcel, the geocode). They carry the fact id in the registry, but the figure is then tier D,
    # so tier-equality is not asserted for them
    input_source_ids: tuple[str, ...] = ()


def _overlay_facts() -> dict[str, FactSpec]:
    return {
        f"overlay.{meta['type']}": FactSpec(
            label=meta.get("name", meta["type"]), source_id=f"chi.zoning.overlay.{meta['type']}",
            method_key="recorded", scope="parcel", tier="official_record",
        )
        for meta in OVERLAY_LAYERS.values()
    }


# Every fact id the Profile emits today. A fact names its source; the registry's ``fact_keys``
# is checked against this in tests/test_provenance.py. Ids are a stable contract: a rename
# ships with a migration map here, because stored answers and reports reference them.
FACTS: dict[str, FactSpec] = {
    "zoning.district": FactSpec("Zoning district", "chi.zoning.districts", "recorded", "parcel", "official_record"),
    "zoning.far": FactSpec("Floor area ratio", "code.hand_table.zoning_definitions", "code_table", "parcel", "official_publication"),
    "zoning.max_height": FactSpec("Maximum building height", "code.hand_table.zoning_definitions", "code_table", "parcel", "official_publication"),
    "zoning.min_lot_area_per_unit": FactSpec("Minimum lot area per dwelling unit", "code.hand_table.zoning_definitions", "code_table", "parcel", "official_publication"),
    **_overlay_facts(),
    "parcel.identity": FactSpec(
        "Parcel identity", "cook.address_points", "recorded", "parcel", "official_record",
        alt_source_ids=("cook.parcel_addresses",), input_source_ids=("cook.parcel_universe", "cook.gis.parcels", "census.geocoder"),
    ),
    "property.land_sqft": FactSpec(
        "Lot area", "cook.assessor.characteristics", "recorded", "parcel", "official_record",
        alt_source_ids=("cook.gis.parcels",), input_source_ids=("cook.ptaxsim",),
    ),
    "property.bldg_sqft": FactSpec(
        "Building area", "cook.assessor.characteristics", "recorded", "parcel", "official_record",
        alt_source_ids=(
            "cook.gis.parcels", "cook.assessor.condo_characteristics", "cook.assessor.commercial_valuation",
            "chi.building_footprints", "chi.energy_benchmarking",
        ),
    ),
    "code.vintage": FactSpec(
        "Municipal Code vintage", "code.municipal_text", "published_text", "city", "official_publication",
        input_source_ids=("code.qdrant_index",),  # the index we answer from must be the same vintage
    ),
}


def weakest_tier(tiers: list[str]) -> str | None:
    """The weakest of ``tiers`` by the guide's A-F order; None for an empty list."""
    known = [t for t in tiers if t in TIER_ORDER]
    return max(known, key=TIER_ORDER.index) if known else None


def _tier_of(ref: str) -> str | None:
    """A calculation's input is a fact id or a registry source id; both resolve to a tier."""
    if ref in FACTS:
        return FACTS[ref].tier
    from backend.data_health.registry import BY_ID

    spec = BY_ID.get(ref)
    return spec.tier if spec and spec.tier != "internal" else None


def resolve_as_of(
    source_id: str | None, *, response_date: str | None = None, response_basis: str | None = None,
) -> tuple[str | None, str]:
    """``(as_of, as_of_basis)`` by the guide's precedence: a date the response carries, then
    data health's latest check, then the registry's frozen vintage, else none and ``queried``.

    The data-health store lands with WS6 M2; the import is guarded so nothing waits on it.
    M2 builds feed only the response date (the registry steps arrive with M3's capture), so
    existing entries keep their v1 ``as_of`` exactly.
    """
    if response_date:
        return response_date, response_basis or "source_updated"
    if source_id:
        try:
            from backend.data_health import status  # type: ignore[attr-defined]

            latest = status.latest(source_id)
            got = latest and (latest.get("content_through") or latest.get("published_at"))
            if got:
                return str(got)[:10], "source_updated"
        except Exception:  # not shipped yet, or the store is unreadable: fall through
            pass
        from backend.data_health.registry import BY_ID

        spec = BY_ID.get(source_id)
        if spec and spec.frozen and _ISO.match(spec.frozen.as_of or ""):
            return spec.frozen.as_of, "vintage"
    return None, "queried"


def _age_days(as_of: str | None, query_date: str) -> int | None:
    if not (as_of and _ISO.match(as_of) and _ISO.match(query_date)):
        return None
    return (date.fromisoformat(query_date) - date.fromisoformat(as_of)).days


def confidence_state(entry: ProvenanceEntry | dict) -> tuple[str, list[str]]:
    """``(state, reasons)`` for one entry, by the guide's §3 rules. The only place these are
    decided; components, prompts and templates read ``confidence`` and never recompute it.

    Reasons that do not change the state (``old_source``) still ride along for the caption.
    """
    e = entry.model_dump() if isinstance(entry, ProvenanceEntry) else entry
    cov = e.get("coverage") or {}
    prec = e.get("precision") or {}
    n, share, sample = cov.get("n"), cov.get("share"), cov.get("sample")
    cv = prec.get("cv")
    hide: list[str] = []
    fade: list[str] = []

    if share is not None:
        if share < HIDE_COVERAGE_BELOW:
            hide.append("low_coverage")
        elif share < FADE_COVERAGE_BELOW:
            fade.append("low_coverage")
    if n is not None and sample == "area_sample" and n < HIDE_N_BELOW:
        hide.append("small_sample")
    if n is not None and sample == "comps":
        if n < COMPS_HIDE_N_BELOW:
            hide.append("small_sample")
        elif n < COMPS_FADE_N_BELOW:
            fade.append("small_sample")
    if cv is not None:
        if cv > HIDE_CV_ABOVE:
            hide.append("high_cv")
        elif cv > FADE_CV_ABOVE:
            fade.append("high_cv")
    if e.get("method_key") == "bracket_median" and prec.get("moe") is None and cv is None:
        fade.append("bracket_median")
    if e.get("tier") == "ai_extracted" or str(e.get("method_key", "")).startswith("ai_read"):
        agr = prec.get("agreement") or {}
        measured = (
            agr.get("n", 0) >= AI_CORROBORATED_MIN_N and agr.get("agree", 0) / agr["n"] >= AI_CORROBORATED_RATE
        )
        if not (e.get("corroborated") or measured):
            fade.append("ai_unverified")

    reasons = list(dict.fromkeys(hide + fade))
    age = e.get("age_days")
    if age is not None and age > OLD_SOURCE_DAYS and e.get("as_of_basis") in _OLD_SOURCE_BASES:
        reasons.append("old_source")
    state = "withheld" if hide else "low" if fade else "standard"
    return state, reasons


def make_entry(
    fact_id: str, *, query_date: str, tier: str | None = None, source_id: str | None = None,
    method_key: str | None = None, scope: str | None = None, label: str | None = None, **fields,
) -> dict:
    """A validated provenance entry as its wire dict. The spec for ``fact_id`` supplies the
    defaults; per-call arguments override (a calculation on a record is not the record's tier).
    ``kind`` is derived from the tier, ``age_days``, ``method``, ``basis_tier`` and the
    confidence state are computed here so no caller can contradict them.
    """
    spec = FACTS.get(fact_id)
    tier = tier or (spec.tier if spec else None)
    method_key = method_key or (spec.method_key if spec else None)
    if tier is None or method_key is None:
        raise KeyError(f"no spec for fact {fact_id!r}: pass tier and method_key")
    as_of = fields.get("as_of")
    fields.setdefault("as_of_basis", "source_updated" if as_of else "queried")
    inputs = fields.get("inputs")
    if inputs and "basis_tier" not in fields:
        fields["basis_tier"] = weakest_tier([t for t in (_tier_of(i) for i in inputs) if t])
    entry = ProvenanceEntry(
        label=label or (spec.label if spec else fact_id),
        kind=_KIND_BY_TIER.get(tier, "derived"),
        query_date=query_date,
        tier=tier,
        source_id=source_id if source_id is not None else (spec.source_id if spec else None),
        method_key=method_key,
        method=fields.pop("method", None) or METHOD_TEXT[method_key],
        scope=scope or (spec.scope if spec else None),
        age_days=_age_days(as_of, query_date),
        **fields,
    )
    entry.confidence, entry.confidence_reasons = confidence_state(entry)
    return entry.to_dict()


def _scalar(v: Any) -> str | int | float | bool | None:
    """A figure as a JSON scalar for ``value``."""
    if v is None or isinstance(v, (str, int, float, bool)):
        return v
    return str(v)


# Which registry source supplied a lot/building area, by the area dataset code on PropertySummary.
_AREA_SOURCE_IDS = {
    "assessor": "cook.assessor.characteristics",
    "gis": "cook.gis.parcels",
    "geometry": "cook.ptaxsim",
    "condo_unit": "cook.assessor.condo_characteristics",
    "commercial_valuation": "cook.assessor.commercial_valuation",
    "footprint": "chi.building_footprints",
    "energy_benchmark": "chi.energy_benchmarking",
}


def _area_basis(fact: str, src: str | None) -> dict:
    """tier/source/method overrides for a lot or building area, by the dataset that supplied it.
    A polygon area is our arithmetic on the County's geometry (tier D on its source's tier), not
    a recorded figure; every other dataset states its area."""
    sid = _AREA_SOURCE_IDS.get(src or "")
    if src == "geometry":
        return {"tier": "our_calculation", "source_id": sid, "method_key": "calculation", "inputs": [sid]}
    return {"source_id": sid} if sid else {}


def build_provenance(
    *,
    context,
    zone_definition: dict | None,
    resolved_pin: str | None,
    resolved_confidence: str | None,
    query_date: str | None = None,
) -> dict[str, dict]:
    """Provenance for the facts the Profile shows. ``context`` is the assembled
    ContextObject; a fact that isn't present gets no entry (never a made-up one)."""
    qd = query_date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    out: dict[str, dict] = {}
    vintage = get_code_vintage()
    zoning = getattr(context, "parcel_zoning", None)

    if zoning is not None:
        out["zoning.district"] = make_entry(
            "zoning.district", query_date=qd,
            label=f"Zoning district {zoning.zone_class}",
            source=ZONING_LAYER,
            record_id=zoning.ordinance_num,
            url=zoning.clerk_url or zoning.zoning_map_url,
            as_of=zoning.map_updated,
            as_of_basis="record_updated" if zoning.map_updated else "queried",
            effective_date=zoning.ordinance_date,
            note=(
                f"Application {zoning.application_num}. " if zoning.application_num else ""
            ) + "as_of is when this district's map record was last edited.",
            geography=zoning.zone_class,
            value=_scalar(zoning.zone_class),
        )

        fam = bulk_family(zoning.zone_class)
        zd = zone_definition or {}
        if fam and not zd.get("is_fallback"):
            for fact, section in BULK_SECTIONS[fam].items():
                if section is None or zd.get(fact) in (None, ""):
                    continue
                out[f"zoning.{fact}"] = make_entry(
                    f"zoning.{fact}", query_date=qd,
                    label=f"{_BULK_LABELS[fact]} for {zoning.zone_class}",
                    source=CODE_SOURCE, record_id=f"§{section}", section=section,
                    as_of=(vintage or {}).get("current_through"), as_of_basis="current_through",
                    note=f"Code text current through {(vintage or {}).get('label')}." if vintage else None,
                    method_params={"section": section},
                    geography=zoning.zone_class,
                    value=_scalar(zd.get(fact)),
                )

    regulatory = getattr(context, "regulatory", None)
    for ov in (regulatory.overlays if regulatory else []):
        lid = _LAYER_ID_BY_TYPE.get(ov.layer_type)
        layer_name = OVERLAY_LAYERS.get(lid, {}).get("name", ov.layer_type) if lid else ov.layer_type
        out[f"overlay.{ov.layer_type}"] = make_entry(
            f"overlay.{ov.layer_type}", query_date=qd,
            label=ov.name or layer_name,
            source=f"City of Chicago Zoning MapServer, {layer_name}" + (f" (layer {lid})" if lid else ""),
            record_id=ov.ordinance or ov.name,
            url=ov.link,
            value=_scalar(ov.name or layer_name),
        )

    if resolved_pin:
        authoritative = resolved_confidence == "authoritative"
        method = (
            "Cook County Address Points or Assessor Parcel Addresses"
            if authoritative
            else "Nearest parcel to the geocoded point (approximate)"
        )
        extra = {} if authoritative else {
            # the nearest parcel is our computation on the Parcel Universe, not a recorded match
            "tier": "our_calculation", "source_id": "cook.parcel_universe", "method_key": "calculation",
            "inputs": ["cook.parcel_universe"],
        }
        out["parcel.identity"] = make_entry(
            "parcel.identity", query_date=qd,
            label=f"Parcel {resolved_pin}",
            source=method, record_id=resolved_pin,
            url=f"https://www.cookcountyassessor.com/pin/{resolved_pin}",
            note=None if authoritative else "Identity not confirmed against an address record.",
            value=resolved_pin,
            **extra,
        )

    prop = getattr(context, "property", None)
    if prop is not None:
        for fact, label, value, src in (
            ("land_sqft", "Lot area", prop.land_sqft, prop.land_sqft_source),
            ("bldg_sqft", "Building area", prop.bldg_sqft, prop.bldg_sqft_source),
        ):
            if value:
                out[f"property.{fact}"] = make_entry(
                    f"property.{fact}", query_date=qd, label=label,
                    source=_AREA_SOURCES.get(src or "", src or "Cook County records"),
                    record_id=prop.pin14,
                    value=_scalar(value),
                    **_area_basis(fact, src),
                )

    if vintage:
        out["code.vintage"] = make_entry(
            "code.vintage", query_date=qd,
            source=vintage.get("source") or CODE_SOURCE, as_of=vintage["current_through"],
            as_of_basis="current_through",
            note=vintage.get("label"),
            value=_scalar(vintage["current_through"]),
        )
    return out


_ISO = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def entry_is_dated(entry: dict | None) -> bool:
    """True when the entry carries at least one valid date saying how current it is."""
    if not entry:
        return False
    return any(isinstance(entry.get(k), str) and _ISO.match(entry[k]) for k in ("as_of", "effective_date", "query_date"))
