"""How far to trust each figure in the $25 report, and the sources table built from it (WS0 M5).

The report reuses the Property Profile's provenance (``build_provenance``) and adds what only the report
has: the zoning cache's setbacks, uses, parking and notes are **read from the code text by AI** (tier E,
"not verified"), and the buildable envelope is our arithmetic on those setbacks. Everything is rendered
through the same quiet-by-default rule as the Profile (guide: ``claude-context/guides/source-confidence.md``
§4): a caption prints only for tiers C-F, low or withheld figures and sources over 24 months old; a
standard official record prints nothing.

Three pure pieces, all taking the report's translator ``t`` so the PDF localizes like the rest:

- ``entries_for_report``: the provenance map for a ``ReportData``;
- ``caption``: the words under a figure (``None`` when quiet), mirroring ``frontend/src/lib/confidence.ts``;
- ``sources_rows``: the Data Sources table, one row per source actually used. No static rows.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Callable

from backend import report_i18n
from backend.data_health.registry import BY_ID
from backend.provenance import TIER_ORDER, build_provenance, make_entry

T = Callable[..., str]

_CAPTIONED_TIERS = {"official_estimate", "our_calculation", "ai_extracted", "non_government"}
_NAMED_SOURCES = {"chi.building_footprints", "private.walkscore", "artifact.chrs",
                  "cook.treasurer.tax_sale", "cook.treasurer.scavenger_sale"}
_SILENT_METHODS = {"recorded", "published_text", "code_table"}
OLD_SOURCE_DAYS = 730


# --- the map ----------------------------------------------------------------------------------------

def entries_for_report(report, ai_meta: dict | None = None, query_date: str | None = None) -> dict[str, dict]:
    """The Profile's provenance for this parcel plus the report-only entries.

    ``ai_meta``: ``{"sections": [...], "code_vintage": "YYYY-MM-DD"}`` from the zoning cache when the standards
    came from an AI extraction (``extraction_confidence`` high or medium); None when they came from the Title 17
    table (then no setback or use is AI-read, and none is claimed)."""
    ctx = report.context
    qd = query_date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    zd = None
    if ctx.parcel_zoning is not None:
        from dataclasses import asdict

        from backend.retrieval.zoning_definitions import get_zone_definition

        zd = asdict(get_zone_definition(ctx.parcel_zoning.zone_class))
    out = build_provenance(
        context=ctx, zone_definition=zd, resolved_pin=report.resolved_pin,
        resolved_confidence=report.resolved_confidence, query_date=qd, comparables=report.comparables,
    )
    s = report.zoning_standards
    if s is None or ai_meta is None or s.extraction_confidence not in ("high", "medium"):
        return out
    section = (ai_meta.get("sections") or [None])[0]
    vintage = ai_meta.get("code_vintage")

    def ai(fact: str, value) -> None:
        out[fact] = make_entry(
            fact, query_date=qd, as_of=vintage, as_of_basis="current_through" if vintage else "queried",
            section=section, value=value if isinstance(value, (str, int, float, bool)) or value is None else str(value),
            note="Read by AI from the district's bulk-and-density section of the Municipal Code; not independently verified.",
        )

    if any(v is not None for v in (s.front_setback_ft, s.side_setback_ft, s.rear_setback_ft)):
        ai("zoning.setbacks", f"{s.front_setback_ft}/{s.side_setback_ft}/{s.rear_setback_ft} ft")
    if s.permitted_uses:
        ai("zoning.permitted_uses", f"{len(s.permitted_uses)} uses")
    if s.special_uses:
        ai("zoning.special_uses", f"{len(s.special_uses)} uses")
    if s.parking_residential or s.parking_commercial:
        ai("zoning.parking", s.parking_residential or s.parking_commercial)
    if s.notes:
        ai("zoning.notes", f"{len(s.notes)} notes")
    if "zoning.setbacks" in out and report.buildable_footprint_sqft:
        out["zoning.envelope"] = make_entry(
            "zoning.envelope", query_date=qd, as_of=None, as_of_basis="queried", value=round(report.buildable_footprint_sqft),
            inputs=["zoning.setbacks", "property.land_sqft"],
            note="Lot area less the AI-read setbacks; a screening drawing, not a survey.",
        )
    return out


# --- captions ----------------------------------------------------------------------------------------

def wants_caption(e: dict | None) -> bool:
    """The default-quiet rule (guide §4.1)."""
    if not e:
        return False
    if e.get("confidence", "standard") != "standard":
        return True
    if e.get("tier") in _CAPTIONED_TIERS:
        return True
    return "old_source" in (e.get("confidence_reasons") or [])


def _fmt_date(iso: str, lang: str) -> str:
    try:
        return report_i18n.format_report_date(date.fromisoformat(iso[:10]), lang)
    except ValueError:
        return iso


def _as_of(e: dict, lang: str) -> str | None:
    if not e.get("as_of") or e.get("as_of_basis") == "queried":
        return None
    if (e.get("age_days") or 0) > OLD_SOURCE_DAYS or e.get("as_of_basis") in ("tax_year", "vintage"):
        return str(e["as_of"])[:4]
    return _fmt_date(e["as_of"], lang)


def _unit(t: T, unit: str | None, n: int | float) -> str:
    """"sale" for one, "sales" otherwise (``conf.unit.<unit>__one`` / ``__other``)."""
    if not unit:
        return ""
    return t(f"conf.unit.{unit}__{'one' if n == 1 else 'other'}")


def _withheld_text(e: dict, t: T) -> str:
    reasons = e.get("confidence_reasons") or []
    cov = e.get("coverage") or {}
    unit = _unit(t, cov.get("unit"), cov.get("n", 0))
    if "small_sample" in reasons:
        return t("conf.withheld.small_sample", n=cov.get("n", 0), unit=unit, min=3 if cov.get("sample") == "comps" else 30)
    if "low_coverage" in reasons:
        return t("conf.withheld.low_coverage", pct=round((cov.get("share") or 0) * 100), min=10)
    if "high_cv" in reasons:
        return t("conf.withheld.high_cv", cv=round(((e.get("precision") or {}).get("cv") or 0) * 100))
    return t("conf.withheld.generic")


def caption(e: dict | None, t: T, lang: str = "en") -> dict | None:
    """``{"ai": bool, "lead": str|None, "text": str, "withheld": bool}`` for a figure, or None when quiet."""
    if not wants_caption(e):
        return None
    assert e is not None
    state = e.get("confidence", "standard")
    if state == "withheld":
        return {"ai": False, "lead": None, "text": _withheld_text(e, t), "withheld": True}
    reasons = e.get("confidence_reasons") or []
    ai = e.get("tier") == "ai_extracted" or str(e.get("method_key", "")).startswith("ai_read")
    parts: list[str] = []
    cov, prec = e.get("coverage") or {}, e.get("precision") or {}
    params = e.get("method_params") or {}

    # Who or how comes first, but a calculation whose basis, period and scope already say what it rests on
    # needs no "our calculation" (mirrors frontend/src/lib/confidence.ts).
    lead_part: str | None = None
    if ai:
        lead_part = t("conf.read_by_ai", section=f"§{e['section']}") if e.get("section") else t("conf.read_by_ai_nosec")
    elif e.get("source_id") in _NAMED_SOURCES:
        lead_part = t("conf.source." + e["source_id"].replace(".", "_"))

    comps = cov.get("sample") == "comps" and isinstance(params.get("radius_mi"), (int, float)) and isinstance(params.get("window_years"), (int, float))
    when = None if comps else (e.get("period") or (None if e.get("method_key") == "calculation" else _as_of(e, lang)))
    if when:
        parts.append(str(when))
    if prec.get("moe") is not None:
        parts.append(f"±{prec['moe']:,.0f}" if prec["moe"] >= 10 else f"±{prec['moe']}")
    elif "bracket_median" in reasons:
        parts.append(t("conf.no_margin"))
    elif "high_cv" in reasons and prec.get("cv") is not None:
        parts.append(t("conf.wide_margin", cv=round(prec["cv"] * 100)))
    if cov.get("n") is not None and cov.get("unit"):
        parts.append(t("conf.sample_n", n=f"{cov['n']:,}", unit=_unit(t, cov["unit"], cov["n"])))
    if comps:
        base = t("conf.comps_basis", radius=f"{params['radius_mi']:.2f}".rstrip("0").rstrip("."), years=int(params["window_years"]))
        parts.append(base + (" " + t("conf.widened") if params.get("widened") else ""))
    if cov.get("share") is not None:
        parts.append(t("conf.coverage", pct=round(cov["share"] * 100)))
    if e.get("geography") and e.get("scope") in ("tract", "community_area", "city", "county"):
        parts.append(str(e["geography"]))
    if e.get("basis_tier") == "ai_extracted":
        parts.append(t("conf.built_on_ai"))
    if ai and "ai_unverified" in reasons:
        parts.append(t("conf.not_verified"))
    if lead_part is None and e.get("method_key") and e["method_key"] not in _SILENT_METHODS \
            and not (e["method_key"] == "calculation" and parts):
        lead_part = t(f"conf.method.{e['method_key']}")
    if lead_part:
        parts.insert(0, lead_part)
    only_ai_reasons = all(r in ("ai_unverified", "old_source") for r in reasons)
    lead = t("conf.low") if state == "low" and not (ai and only_ai_reasons) else None
    return {"ai": ai, "lead": lead, "text": " · ".join(parts), "withheld": False}


# --- the sources table -------------------------------------------------------------------------------

_TIER_RANK = {tier: i for i, tier in enumerate(TIER_ORDER)}


def _period_text(period: str) -> str:
    """"2003–2003" is just "2003" (a one-year span the backend wrote as a range)."""
    a, sep, b = period.partition("–")
    return a if sep and a == b else period


def _group_as_of(entries: list[dict], t: T, lang: str) -> str:
    """How current a source is, for the table: the newest record date, or the period of a survey or tax year
    (an ACS estimate is "2020–2024", not "December 31, 2024"); "queried <date>" when the publisher gives none."""
    periodic = [e for e in entries if e.get("period") and e.get("as_of_basis") in ("tax_year", "period_end") and e.get("as_of")]
    if periodic:
        return _period_text(max(periodic, key=lambda e: str(e["as_of"]))["period"])
    dates = sorted(str(e["as_of"])[:10] for e in entries if e.get("as_of") and e.get("as_of_basis") != "queried")
    if dates:
        return _fmt_date(dates[-1], lang)
    named = [e["period"] for e in entries if e.get("period")]
    if named:
        return _period_text(named[0])
    return t("conf.as_of_queried", date=_fmt_date(max(e.get("query_date") or "" for e in entries), lang))


def sources_rows(provenance: dict[str, dict], t: T, lang: str = "en", max_used: int = 5) -> list[dict]:
    """One row per source the report actually used: its name, publisher, authority class, how current, and the
    figures it supplied. Built from the provenance map, so a source the report did not use is not listed."""
    groups: dict[str, list[dict]] = {}
    for e in provenance.values():
        sid = e.get("source_id")
        if sid:
            groups.setdefault(sid, []).append(e)
    rows = []
    for sid, entries in groups.items():
        spec = BY_ID.get(sid)
        tier = spec.tier if spec else (entries[0].get("tier") or "official_record")
        name = (spec.displayed_label or spec.name) if spec else (entries[0].get("source") or sid)
        as_of = _group_as_of(entries, t, lang)
        labels = list(dict.fromkeys(e["label"] for e in entries if e.get("label")))
        used = ", ".join(labels[:max_used]) + (" " + t("conf.more", n=len(labels) - max_used) if len(labels) > max_used else "")
        rows.append({
            "source_id": sid, "name": name, "publisher": spec.publisher if spec else "", "tier": tier,
            "authority": t(f"conf.tier.{tier}") if tier in _TIER_RANK or tier == "internal" else tier,
            "as_of": as_of, "used": used, "n": len(entries),
        })
    rows.sort(key=lambda r: (_TIER_RANK.get(r["tier"], len(_TIER_RANK)), r["name"]))
    return rows


def state(e: dict | None) -> str:
    """The confidence state of a figure, ``standard`` when it has no entry."""
    return (e or {}).get("confidence", "standard")


def helpers(provenance: dict[str, dict] | None, t: T, lang: str, code_currency: dict | None = None) -> dict[str, Any]:
    """Jinja globals bound to one report: ``conf_caption(fact)``, ``conf_state(fact)``, the sources rows and
    ``data_dates()``, the cover's "Data as of" list (the same dates the chat footer and the Profile show)."""
    from backend.data_health.vintages import phrases, vintages_for

    prov = provenance or {}
    tn = report_i18n.make_plural(lang)
    return {
        "conf_caption": lambda fact: caption(prov.get(fact), t, lang),
        "conf_state": lambda fact: state(prov.get(fact)),
        "sources_rows": lambda: sources_rows(prov, t, lang),
        "data_dates": lambda: phrases(vintages_for(prov, code_currency=code_currency), t, tn, lambda iso: _fmt_date(iso, lang)),
    }
