"""Cook County assessment levels by property class.

Assessment level = assessed value ÷ market value, set by county ordinance
(Code of Ordinances Sec. 74-64). Market value and effective tax rate MUST be
derived through the class's own level: applying the 10% residential level to
a class-5 commercial parcel overstates its implied market value 2.5× and
understates its effective tax rate by the same factor (caught live on
4520 N Clark, class 517: shown 2.06%, true ~5.15%).
"""

# Level by leading class digit. Vacant (1), residential (2), and multifamily
# (3) assess at 10%; not-for-profit (4) at 20%; commercial/industrial (5) at
# 25%; incentive classes (6/7/8/9) at 10% — the reduced level is the incentive.
_LEVEL_BY_PREFIX = {
    "1": 0.10,
    "2": 0.10,
    "3": 0.10,
    "4": 0.20,
    "5": 0.25,
    "6": 0.10,
    "7": 0.10,
    "8": 0.10,
    "9": 0.10,
}


def assessment_level_for_class(bldg_class: str | None) -> float | None:
    """Ordinance assessment level for a CCAO class code ("517", "2-11", "203"),
    or None when the class is unknown, exempt (EX), or railroad (RR)."""
    if not bldg_class:
        return None
    code = str(bldg_class).strip().upper()
    if not code or code.startswith(("EX", "RR")):
        return None
    return _LEVEL_BY_PREFIX.get(code[0])
