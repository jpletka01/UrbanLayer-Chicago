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


# A nominal assessment is a placeholder, not a valuation: the County carries common areas and remnants of
# divided lots at a token amount (Illinois lists a qualifying subdivision common area at $1 a year and
# counts its value in the lots that share it, 35 ILCS 200/10-35). 2,533 of the 882,328 indexed parcels sit
# at $1-$99 (2026-11-01, decision Item 46). Market value, tax and $/ft² divided out of such a number are
# meaningless, so every surface states the fact instead of showing the figure.
NOMINAL_ASSESSED_BELOW = 100.0
# A real prior value that fell more than 99% is the same placeholder arriving mid-history.
NOMINAL_DROP_SHARE = 0.01
NOMINAL_PRIOR_MIN = 10_000.0


def is_nominal_assessment(
    total: float | None, bldg_class: str | None = None, *, prior_total: float | None = None
) -> bool:
    """True when ``total`` is a token assessment rather than a value: under $100, or under 1% of a prior
    real total (≥ $10,000). Exempt (EX) and railroad (RR) classes have their own states and never qualify."""
    if total is None:
        return False
    code = str(bldg_class or "").strip().upper()
    if code.startswith(("EX", "RR")):
        return False
    if total < NOMINAL_ASSESSED_BELOW:
        return True
    return bool(prior_total and prior_total >= NOMINAL_PRIOR_MIN and total < prior_total * NOMINAL_DROP_SHARE)


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
