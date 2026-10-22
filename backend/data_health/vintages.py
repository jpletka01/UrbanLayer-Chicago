"""The data dates behind an answer, a report or a Profile (WS6 M6, plan §4.1).

One builder, three surfaces. ``vintages_for`` reads a provenance map (``backend/provenance.py``: every
figure's source, date and period, already resolved through the data-health store and the registry) and
returns the handful of dates a reader should see: when the zoning map record was last edited, how current
the code text is (and what has passed since), the Assessor's value year, the tax year, how far the sales
and the area feeds run, the ACS release. The chat footer, the report cover and the Profile footer all
show this list, so they cannot disagree.

A date we do not have is never invented. A figure whose source gave no date still gets an entry, of kind
``checked``, carrying the day we asked ("311 checked Oct 22, 2026"), so the reader sees the difference
between "current through" and "we looked on".

Pure over dicts: no request, no model. The wording lives in the callers' catalogs (``dates.*`` in
``report_i18n.py`` for chat and the PDF, ``scorecard.dates.*`` in the frontend locales); this module
decides *which* dates, in what order, and of which kind.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Callable, Literal

Kind = Literal["record", "through", "period", "checked"]

# Fact ids whose presence says the answer rests on the Municipal Code (the code vintage alone, on a
# crime question, would be a date nobody asked for).
_CODE_FACTS = ("zoning.district", "zoning.far", "zoning.max_height", "zoning.min_lot_area_per_unit")


@dataclass(frozen=True)
class DatedSource:
    key: str
    kind: Kind
    source_id: str | None
    as_of: str | None  # ISO day; for ``checked`` the day we asked
    period: str | None = None  # "2020–2024", "2025" for a survey or tax year
    url: str | None = None
    # code text only: amendments passed since. ``None`` count = we could not check recently.
    since: int | None = None
    since_state: str | None = None  # fresh | aging | unknown
    since_checked_at: str | None = None

    def to_dict(self) -> dict:
        return {k: v for k, v in asdict(self).items() if v is not None}


def _first(prov: dict[str, dict], *fact_ids: str) -> dict | None:
    for f in fact_ids:
        if f in prov:
            return prov[f]
    return None


def _first_prefix(prov: dict[str, dict], prefix: str) -> dict | None:
    return next((e for k, e in prov.items() if k.startswith(prefix)), None)


def _dated(key: str, e: dict, *, record: bool = False) -> DatedSource:
    """A source-level or record-level date, or the day we asked when the source gave none."""
    as_of = e.get("as_of")
    if as_of and e.get("as_of_basis") != "queried":
        return DatedSource(key, "record" if record else "through", e.get("source_id"), str(as_of)[:10], url=e.get("url"))
    return DatedSource(key, "checked", e.get("source_id"), e.get("query_date"))


def _period(key: str, e: dict) -> DatedSource:
    """A survey or tax year: the period is the date. Without one, the day we asked."""
    if e.get("period"):
        return DatedSource(key, "period", e.get("source_id"), str(e["as_of"])[:10] if e.get("as_of") else None, period=str(e["period"]))
    return DatedSource(key, "checked", e.get("source_id"), e.get("query_date"))


# (key, fact ids to read in order, builder)
_AREA_FEEDS = (
    ("crime", ("area.crime",)),
    ("c311", ("area.311",)),
    ("permits", ("area.permits",)),
    ("violations", ("area.violations", "property.violations")),
    ("business", ("area.business",)),
    ("vacant", ("area.vacant",)),
    ("food", ("area.food",)),
)


def vintages_for(provenance: dict[str, dict] | None, *, code_currency: dict | None = None) -> list[DatedSource]:
    """The dates behind these figures, in reading order: the parcel's (zoning map, code text, Assessor,
    tax, sales), then the area's (census, crime, 311...). ``provenance`` is a ``{fact_id: entry}`` map;
    ``code_currency`` (WS1) adds what Council has passed since the code text."""
    prov = provenance or {}
    out: list[DatedSource] = []

    zd = prov.get("zoning.district")
    if zd:
        out.append(_dated("zoning_map", zd, record=True))

    cv = prov.get("code.vintage")
    if cv and any(f in prov for f in _CODE_FACTS):
        item = _dated("code_text", cv)
        cc = code_currency or {}
        if cc.get("current_through") and cc.get("check_state") in ("fresh", "aging", "unknown"):
            since = (cc.get("since") or {}).get("title17")
            item = DatedSource(
                item.key, item.kind, item.source_id, item.as_of, url=item.url,
                since=since if cc["check_state"] != "unknown" else None,
                since_state=cc["check_state"], since_checked_at=cc.get("checked_at"),
            )
        out.append(item)

    av = prov.get("property.assessed_value")
    if av:
        out.append(_period("assessor", av))
    tx = prov.get("property.tax_estimate")
    if tx:
        out.append(_period("tax_year", tx))
    sales = _first(prov, "property.sales") or _first_prefix(prov, "property.comps.")
    if sales:
        out.append(_dated("sales", sales))

    tract = _first_prefix(prov, "area.tract.")
    if tract:
        out.append(_period("acs_tract", tract))
    ca = _first(prov, "area.community_area.population", "area.community_area.median_household_income")
    if ca:
        out.append(_period("acs_community_area", ca))

    for key, facts in _AREA_FEEDS:
        e = _first(prov, *facts)
        if e:
            out.append(_dated(key, e))
    return out


# --- wording, shared by chat and the PDF (the Profile words the same dates in the frontend locales) ----------

Translator = Callable[..., str]


def phrase(d: DatedSource, t: Translator, tn: Callable[..., str], fmt: Callable[[str], str]) -> str:
    """"Crime through Oct 14, 2026", "ACS (tract) 2020–2024", "311 checked Oct 22, 2026". ``t``/``tn`` are the
    report catalog's translator and plural translator; ``fmt`` formats an ISO day for the reader's language."""
    noun = t(f"dates.noun.{d.key}")
    value = d.period if d.kind == "period" and d.period else (fmt(d.as_of) if d.as_of else "")
    text = t(f"dates.{d.kind}", noun=noun, v=value)
    if d.key == "code_text":
        if d.since is not None:
            text += " " + tn("dates.since_aging" if d.since_state == "aging" else "dates.since", d.since,
                             d=fmt(d.since_checked_at) if d.since_checked_at else "")
        elif d.since_state == "unknown":
            text += " " + t("dates.since_unknown")
    return text


def phrases(items: list[DatedSource], t: Translator, tn: Callable[..., str], fmt: Callable[[str], str],
            skip: set[str] | None = None) -> list[str]:
    return [phrase(d, t, tn, fmt) for d in items if not skip or d.key not in skip]


def as_dicts(items: list[DatedSource]) -> list[dict[str, Any]]:
    return [d.to_dict() for d in items]
