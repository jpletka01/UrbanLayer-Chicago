"""What "we couldn't check" is called, once (WS6 M7, plan §4.2).

Every surface that says a source didn't answer (the Profile's modules and verdict caveat, the chat footer,
the report cover and sections) draws from this one table, so they agree on what failed and where it shows.
``partial_failures`` stays the list of plain-words labels the model and the page already carry; this adds
the stable *keys* behind them and the module each belongs to, so a surface can say "couldn't check property
records" in the module that would otherwise have gone quiet, instead of one line far from it.

Pure: no request, no model.
"""

from __future__ import annotations

from typing import Iterable

# key -> the label that goes in ``partial_failures`` (plain words, singular noun phrase).
LABELS: dict[str, str] = {
    "property": "property records",
    "regulatory": "regulatory overlays",
    "flood": "FEMA flood zone",
    "zoning": "parcel zoning",
    "incentives": "incentive zones",
    "neighborhood": "demographics and transit",
    "aro_housing": "affordable housing data",
    "crime": "crime statistics",
    "crime_yoy": "crime year-over-year comparison",
    "violations": "building violations",
    "address_311": "address 311 complaints",
    "comparables": "comparable sales",
    "311": "311 service requests",
    "permits": "building permits",
    "business": "business licenses",
    "vacant": "vacant buildings",
    "food_inspections": "food inspections",
    "adjacent_zoning": "adjacent zoning",
    "address_permits": "address-specific permits",
    "address_violations": "address-specific violations",
    "nearby_construction": "nearby construction activity",
}

# A retrieval task's own name, where it differs from the key.
ALIASES: dict[str, str] = {"zoning_lookup": "zoning", "comparable_sales": "comparables"}

# Where a failure shows: the Profile module (and, in the report, the section) whose figures it leaves out.
# ``build`` = zoning and overlays, ``economics`` = the parcel's records and incentives, ``market`` = comps and
# nearby sales, ``record`` = violations, 311 and permits at the address, and the flood zone, ``area`` = the neighborhood. These are the
# Profile's module ids (``module-<name>``), so the frontend table must match (a pytest pins it).
MODULES: dict[str, str] = {
    "zoning": "build", "regulatory": "build", "adjacent_zoning": "build",
    "property": "economics", "incentives": "economics",
    "comparables": "market", "nearby_construction": "market",
    "violations": "record", "address_311": "record", "address_permits": "record", "address_violations": "record",
    "flood": "record",  # the flood zone is shown on the Environment card, in "what to watch for"
    "crime": "area", "crime_yoy": "area", "neighborhood": "area", "aro_housing": "area", "311": "area",
    "permits": "area", "business": "area", "vacant": "area", "food_inspections": "area",
}

# Sub-sources a domain reports as ``data_gaps`` (it succeeded, one part did not).
_GAP_PROPERTY = {"property characteristics", "property assessments", "property sales history", "property tax estimate"}
_OVERLAY_SUFFIX = "(City zoning map didn't answer)"

_BY_LABEL = {label: key for key, label in LABELS.items()}


def key_for(task: str) -> str:
    """The key for a retrieval task's name (``zoning_lookup`` is ``zoning``)."""
    return ALIASES.get(task, task)


def label(task: str) -> str:
    """The ``partial_failures`` label for a retrieval task's name."""
    return LABELS[key_for(task)]


def key_for_label(text: str) -> str | None:
    """The key behind a ``partial_failures`` string, or None for one this table does not name."""
    if text in _BY_LABEL:
        return _BY_LABEL[text]
    if text.endswith(_OVERLAY_SUFFIX):
        return "regulatory"
    if text in _GAP_PROPERTY:
        return "property"
    return None


def failed_keys(partial_failures: Iterable[str] | None) -> list[str]:
    """The distinct keys behind ``partial_failures``, in first-seen order."""
    return list(dict.fromkeys(k for s in (partial_failures or []) if (k := key_for_label(s))))


def failed_detail(partial_failures: Iterable[str] | None) -> list[dict]:
    """``[{"key", "labels"}]``: each failed source with the exact words that reported it ("property tax estimate"
    for a gap inside records that otherwise answered), in first-seen order. The Profile places each by ``key``
    and words it by ``labels``."""
    out: dict[str, list[str]] = {}
    for s in partial_failures or []:
        k = key_for_label(s)
        if k:
            out.setdefault(k, [])
            if s not in out[k]:
                out[k].append(s)
    return [{"key": k, "labels": v} for k, v in out.items()]


def in_module(keys: Iterable[str], module: str) -> list[str]:
    """The failed keys whose figures belong to ``module``."""
    return [k for k in keys if MODULES.get(k) == module]
