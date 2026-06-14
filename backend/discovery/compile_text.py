"""Deterministic text compiler (04.3) — `text → CqsFragment` (source:"text") + residual.

A rule/grammar-based parser, NOT the LLM: the LLM is non-deterministic and would break
INV-2. `parse` is total and deterministic — the same string always yields the same
fragment. Every assignment conforms to the registry predicate kind; tokens it cannot map
go to `meta.textResidual` and MUST NOT constrain results (INV-5). It lives in one place
(backend) so all clients parse identically.

The lexicon/grammar below is an intentionally small, *unambiguous* seed (plain data,
extensible without touching the evaluator). It is deliberately conservative: anything it
is not confident about is left as residual rather than guessed.
"""

from __future__ import annotations

import re

from backend.discovery.cqs import (
    CqsFragment,
    EnumPredicate,
    FilterAssignment,
    FlagPredicate,
    QueryMeta,
    RangePredicate,
)


def _to_int(raw: str) -> int:
    return int(raw.replace(",", ""))


# --- Range grammar -----------------------------------------------------------
# Each rule: (compiled regex, builder(match) -> (filter_id, RangePredicate)). Bounds
# from separate matches for the same filter are merged (first-set wins per bound), so
# "at least 5 units and under 20 units" → units[min=5, max=20]. `between` rules are
# ordered first so they consume their span before the open-ended rules can re-match it.

_SQFT = r"(?:sq\.?\s?ft|sf|square feet|sqft)"

_RANGE_RULES: list[tuple[re.Pattern[str], object]] = [
    # year_built
    (re.compile(r"built between (\d{4}) and (\d{4})"),
     lambda m: ("year_built", RangePredicate(min=int(m.group(1)), max=int(m.group(2))))),
    (re.compile(r"built (?:after|since)\s+(\d{4})"),
     lambda m: ("year_built", RangePredicate(min=int(m.group(1))))),
    (re.compile(r"(?:newer than)\s+(\d{4})"),
     lambda m: ("year_built", RangePredicate(min=int(m.group(1))))),
    (re.compile(r"built before\s+(\d{4})"),
     lambda m: ("year_built", RangePredicate(max=int(m.group(1))))),
    (re.compile(r"(?:older than)\s+(\d{4})"),
     lambda m: ("year_built", RangePredicate(max=int(m.group(1))))),
    # units
    (re.compile(r"(\d+)\+\s+units"),
     lambda m: ("units", RangePredicate(min=int(m.group(1))))),
    (re.compile(r"(?:at least|over|more than)\s+(\d+)\s+units"),
     lambda m: ("units", RangePredicate(min=int(m.group(1))))),
    (re.compile(r"(?:under|fewer than|less than|at most|up to)\s+(\d+)\s+units"),
     lambda m: ("units", RangePredicate(max=int(m.group(1))))),
    # lot_size (requires a sqft unit so a bare number is never silently a lot size)
    (re.compile(rf"lot (?:over|at least|more than|min(?:imum)?(?: of)?)\s+([\d,]+)\s*{_SQFT}"),
     lambda m: ("lot_size", RangePredicate(min=_to_int(m.group(1))))),
    (re.compile(rf"lot (?:under|at most|less than|max(?:imum)?(?: of)?)\s+([\d,]+)\s*{_SQFT}"),
     lambda m: ("lot_size", RangePredicate(max=_to_int(m.group(1))))),
]


# --- Phrase lexicon ----------------------------------------------------------
# Flag phrases all emit flag=True. Enum phrases emit (filter_id, value). Ambiguous bare
# words (e.g. "residential", "commercial" — land_use vs zoning_group) are intentionally
# omitted; only qualified phrases ("zoned residential") map to zoning_group.

_FLAG_PHRASES: dict[str, str] = {
    "tax increment financing": "tif",
    "tax increment": "tif",
    "tif": "tif",
    "opportunity zone": "opportunity_zone",
    "enterprise zone": "enterprise_zone",
    "neighborhood opportunity fund": "sbif_nof",
    "sbif": "sbif_nof",
    "nof": "sbif_nof",
    "accessory dwelling": "adu_eligible",
    "adu eligible": "adu_eligible",
    "adu": "adu_eligible",
    "aro zone": "aro_zone",
    "aro": "aro_zone",
    "floodplain": "floodplain",
    "flood plain": "floodplain",
    "flood zone": "floodplain",
    "brownfield": "brownfield",
    "vacant lot": "vacancy",
    "vacant site": "vacancy",
    "vacant": "vacancy",
    "vacancy": "vacancy",
}

_ENUM_PHRASES: dict[str, tuple[str, str]] = {
    "multifamily": ("land_use", "multi_family"),
    "multi-family": ("land_use", "multi_family"),
    "multi family": ("land_use", "multi_family"),
    "single family": ("land_use", "residential"),
    "single-family": ("land_use", "residential"),
    "warehouse": ("land_use", "industrial"),
    "industrial building": ("land_use", "industrial"),
    "mixed use": ("land_use", "mixed_use"),
    "mixed-use": ("land_use", "mixed_use"),
    "zoned residential": ("zoning_group", "residential"),
    "residential zoning": ("zoning_group", "residential"),
    "zoned commercial": ("zoning_group", "commercial"),
    "commercial zoning": ("zoning_group", "commercial"),
    "zoned manufacturing": ("zoning_group", "manufacturing"),
    "manufacturing zoning": ("zoning_group", "manufacturing"),
    "zoned business": ("zoning_group", "business"),
    "business zoning": ("zoning_group", "business"),
    "downtown zoning": ("zoning_group", "downtown"),
}

# All phrases longest-first so "vacant lot" wins over "vacant", etc.
_PHRASES_BY_LEN: list[str] = sorted(
    set(_FLAG_PHRASES) | set(_ENUM_PHRASES), key=len, reverse=True
)

_STOPWORDS = {
    "in", "with", "and", "or", "the", "a", "an", "of", "for", "me", "find", "show",
    "get", "list", "parcels", "parcel", "properties", "property", "that", "are", "is",
    "near", "to", "my", "all", "any", "give",
}
_WORD = re.compile(r"[a-z0-9]+")


def _merge_range(cur: RangePredicate | None, new: RangePredicate) -> RangePredicate:
    """Fill missing bounds from `new`; an already-set bound wins (first-set, deterministic)."""
    if cur is None:
        return new
    return RangePredicate(
        min=cur.min if cur.min is not None else new.min,
        max=cur.max if cur.max is not None else new.max,
    )


def parse(text: str) -> CqsFragment:
    if not text or not text.strip():
        return CqsFragment(meta=QueryMeta(rawText=text or None))

    s = text.lower()
    consumed = bytearray(len(s))  # 1 where a char belongs to a matched span

    def is_free(start: int, end: int) -> bool:
        return not any(consumed[start:end])

    def mark(start: int, end: int) -> None:
        for i in range(start, end):
            consumed[i] = 1

    range_acc: dict[str, RangePredicate] = {}
    enum_acc: dict[str, list[str]] = {}
    flags: dict[str, FilterAssignment] = {}

    # 1) structured range grammar (ordered; spans consumed greedily)
    for rx, builder in _RANGE_RULES:
        for m in rx.finditer(s):
            if not is_free(m.start(), m.end()):
                continue
            fid, pred = builder(m)  # type: ignore[operator]
            range_acc[fid] = _merge_range(range_acc.get(fid), pred)
            mark(m.start(), m.end())

    # 2) phrase lexicon (longest-first, word-boundary)
    for phrase in _PHRASES_BY_LEN:
        for m in re.finditer(rf"\b{re.escape(phrase)}\b", s):
            if not is_free(m.start(), m.end()):
                continue
            if phrase in _FLAG_PHRASES:
                fid = _FLAG_PHRASES[phrase]
                flags.setdefault(
                    fid, FilterAssignment(predicate=FlagPredicate(value=True), source="text")
                )
            else:
                fid, value = _ENUM_PHRASES[phrase]
                enum_acc.setdefault(fid, [])
                if value not in enum_acc[fid]:
                    enum_acc[fid].append(value)
            mark(m.start(), m.end())

    filters: dict[str, FilterAssignment] = {}
    for fid, pred in range_acc.items():
        filters[fid] = FilterAssignment(predicate=pred, source="text")
    for fid, values in enum_acc.items():
        filters[fid] = FilterAssignment(predicate=EnumPredicate(values=sorted(values)), source="text")
    filters.update(flags)

    residual = [
        m.group(0)
        for m in _WORD.finditer(s)
        if not any(consumed[m.start():m.end()]) and m.group(0) not in _STOPWORDS
    ]
    return CqsFragment(filters=filters, meta=QueryMeta(rawText=text, textResidual=residual))
