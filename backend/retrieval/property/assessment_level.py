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


# The Profile's "class norm" effective tax rate = CLASS_NORM_RATE_PER_LEVEL x the class's assessment level
# (frontend ScorecardPage.tsx holds the same constant; a test pins them together). It is the Chicago
# composite rate (the most common one, 6.995%) times the state equalizer (3.0163), both for tax year 2023,
# and so reads 0.2110. The same arithmetic on tax year 2024 (6.6186% x 3.0355) gives 0.2009: the constant
# runs about 5% high against the newest bill year. Both figures were read from ptaxsim on 2026-10-21.
CLASS_NORM_RATE_PER_LEVEL = 0.21
CLASS_NORM_TAX_YEAR = 2023
CLASS_NORM_NOTE = (
    "Chicago's most common composite tax rate (6.995%) times the state equalizer (3.0163), tax year 2023, "
    "times the class's assessment level. The same arithmetic on tax year 2024 gives 0.2009, so this norm "
    "runs about 5% high against the newest bill year."
)
