"""The break-even calculator's starting numbers (Deep analysis, decision Item 124).

Every number the tab starts from carries where it came from, its range when there is one, and a date. Two kinds:

* **The lot's own figures**, read from the Profile's data: its last recorded sale, the area's sale prices by building
  type (Assessor sales by community area and year), rents by bedroom (the Census tract, HUD's ZIP-level voucher
  standard), and the effective tax rate (the parcel's tax code, as the Profile shows it).
* **Assumptions with no public source for this lot** (build cost, soft costs, loans, selling costs, operating costs,
  cap rates, a profit target): defaults from the research behind Item 124, each with its range and source named, and
  always editable on the page. Build cost is the one the answer rests on; its range is what builders report (2025),
  and the page asks for the builder's own contractor number.

Nothing here calls a model or the network; the lot's figures come from the report's already-assembled context.
"""

from __future__ import annotations

from typing import Any

# Assumptions: (default, low, high, source, as_of). Research: research/reports/Developer pencil math needs.md (local).
ASSUMPTIONS: dict[str, dict[str, Any]] = {
    "build_cost_sqft": {"value": 250, "low": 200, "high": 275, "unit": "usd_per_sqft",
                        "source": "builders_reported", "as_of": "2025"},
    "soft_cost_pct": {"value": 0.18, "low": 0.15, "high": 0.25, "unit": "share_of_hard",
                      "source": "terner_2024", "as_of": "2024"},
    "loan_to_cost": {"value": 0.65, "low": 0.60, "high": 0.75, "unit": "share", "source": "lenders_2026", "as_of": "2026"},
    "loan_rate": {"value": 0.09, "low": 0.0775, "high": 0.1175, "unit": "rate", "source": "lenders_2026", "as_of": "2026"},
    "build_months": {"value": 14, "low": 10, "high": 24, "unit": "months", "source": "lenders_2026", "as_of": "2026"},
    "selling_pct": {"value": 0.06, "low": 0.04, "high": 0.08, "unit": "share_of_sale", "source": "common_practice", "as_of": "2026"},
    "profit_on_cost": {"value": 0.20, "low": 0.15, "high": 0.25, "unit": "share", "source": "developer_rule", "as_of": "2026"},
    "vacancy_pct": {"value": 0.05, "low": 0.03, "high": 0.08, "unit": "share", "source": "common_practice", "as_of": "2026"},
    "opex_pct": {"value": 0.30, "low": 0.25, "high": 0.40, "unit": "share_of_income", "source": "common_practice", "as_of": "2026"},
    "cap_rate": {"value": 0.0625, "low": 0.055, "high": 0.07, "unit": "rate", "source": "chicago_brokers_2026", "as_of": "2026"},
    "target_yield": {"value": 0.0775, "low": 0.07, "high": 0.09, "unit": "rate", "source": "spread_rule", "as_of": "2026"},
}

# A floor is about 11 ft (a residential story with its structure); the page says so where it counts floors.
FLOOR_FT = 11


def _last_sale(prop: Any) -> dict | None:
    """The newest recorded sale with a price a market sale could have (not a $1 or under-$10,000 transfer)."""
    sales = [s for s in (getattr(prop, "sales_history", None) or []) if s.price and s.price >= 10_000 and s.date]
    if not sales:
        return None
    s = max(sales, key=lambda r: r.date)
    return {"price": s.price, "date": s.date[:10], "deed_type": s.deed_type}


def _area_sales(rent: Any) -> dict:
    """The community area's latest median sale price per building type (condo, 2–6 units, single-family), with n."""
    out: dict[str, Any] = {}
    trend = getattr(rent, "sales_trend", None)
    if not trend:
        return out
    for group, rows in (trend.groups or {}).items():
        if rows:
            last = rows[-1]
            out[group] = {"median": last.median, "n": last.n, "year": last.year}
    return out


def _rents(rent: Any, zip_code: str | None) -> dict:
    """Rents by bedroom: the tract's (or PUMA's) Census medians with their margins, and HUD's ZIP standard."""
    out: dict[str, Any] = {"census": {}, "hud": None, "acs_period": getattr(rent, "acs_period", None) if rent else None}
    for b in (getattr(rent, "bedrooms", None) or []):
        if b.estimate:
            out["census"][b.bedrooms] = {"estimate": b.estimate, "moe": b.moe, "scope": b.scope}
    hud = getattr(rent, "safmr", None) if rent else None
    if hud is None and zip_code:
        try:
            from backend.retrieval.neighborhood.rent import safmr_for_zip
            hud = safmr_for_zip(zip_code)
        except Exception:
            hud = None
    if hud is not None and getattr(hud, "listed", False):
        out["hud"] = {"by_bedroom": hud.by_bedroom, "fy": hud.fy, "zip": hud.zip_code}
    return out


def build_inputs(report: Any) -> dict:
    """The calculator's starting numbers for one lot. Pure over the report's context."""
    ctx = report.context
    prop = ctx.property
    nbr = ctx.neighborhood
    rent = getattr(nbr, "rent", None) if nbr else None
    zoning = report.zoning_standards
    unit_yield = report.unit_yield or {}
    return {
        "lot": {
            "land_sqft": prop.land_sqft if prop else None,
            "far": zoning.far if zoning else None,
            "max_height_ft": zoning.max_height_ft if zoning else None,
            "units_allowed": unit_yield.get("units"),
            "lot_area_per_unit": unit_yield.get("mla_per_unit"),
            "footprint_sqft": report.buildable_footprint_sqft,
        },
        "last_sale": _last_sale(prop) if prop else None,
        "area_sales": _area_sales(rent),
        "rents": _rents(rent, getattr(prop, "zip_code", None) if prop else None),
        "tax": {
            # The parcel's effective rate on market value (assessment level × equalizer × its tax code's rate), the
            # same figure the Profile shows; None for an exempt parcel, where the page asks for the rate.
            "effective_rate": report.effective_tax_rate,
            "tax_year": getattr(prop, "tax_year", None) if prop else None,
            "current_bill": getattr(prop, "estimated_annual_tax", None) if prop else None,
        },
        "assumptions": ASSUMPTIONS,
        "floor_ft": FLOOR_FT,
    }
