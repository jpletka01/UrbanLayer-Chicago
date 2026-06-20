"""Guards for the deterministic report i18n catalog (backend/report_i18n.py).

The 2026-06-20 language-flexibility work externalized the $25 feasibility report's
text into a per-language catalog. These tests lock in the invariants that keep
en/es from drifting (the class of bug that produced "3 of 5 zones" vs
"3 of 3 zones" on the frontend) and that the translator behaves safely.
"""
from datetime import date

import pytest

from backend import report_i18n as R


def test_en_es_key_parity():
    """Every catalog key must exist in both languages — no silent English leak."""
    en, es = set(R._EN), set(R._ES)
    assert en - es == set(), f"keys missing from ES: {sorted(en - es)}"
    assert es - en == set(), f"keys missing from EN: {sorted(es - en)}"


def test_plural_variants_paired():
    """A ``__one`` key must have a matching ``__other`` (and vice versa) in both."""
    for lang, cat in (("en", R._EN), ("es", R._ES)):
        ones = {k[:-5] for k in cat if k.endswith("__one")}
        others = {k[:-7] for k in cat if k.endswith("__other")}
        assert ones == others, f"{lang}: unpaired plural keys {ones ^ others}"


def test_translator_falls_back_to_en_then_key():
    t_es = R.make_translator("es")
    # Known key → Spanish
    assert t_es("glossary.tif.term").startswith("TIF")
    assert t_es("exec.heading") == "Resumen Ejecutivo"
    # Unknown language → English
    assert R.make_translator("fr")("exec.heading") == "Executive Summary"
    # Unknown key → returns the key unchanged (never raises)
    assert t_es("does.not.exist") == "does.not.exist"


def test_translator_interpolation_is_safe():
    t = R.make_translator("es")
    assert "RM-5" in t("cover.headline_existing", bldg="1,000", land="3,350", zone="RM-5")
    # Missing interpolation kwargs must not raise — returns the template literal.
    assert t("cover.headline_existing") == R._ES["cover.headline_existing"]


def test_plural_selection_and_no_n_collision():
    tn = R.make_plural("es")
    # Selects the singular/plural variant by count...
    assert tn("site.open_complaints", 1) == "1 queja abierta"
    assert tn("site.open_complaints", 3) == "3 quejas abiertas"
    # ...and passing n= explicitly alongside the positional count must NOT collide.
    assert tn("site.open_complaints", 3, n=3) == "3 quejas abiertas"


def test_format_report_date_localized():
    d = date(2026, 6, 20)
    assert R.format_report_date(d, "en") == "June 20, 2026"
    assert R.format_report_date(d, "es") == "20 de junio de 2026"
    assert R.format_report_date(d, "es-MX") == "20 de junio de 2026"  # tag normalized
    assert R.format_report_date(d, None) == "June 20, 2026"


@pytest.mark.parametrize("lang,expected", [("en", "en"), ("es", "es"), ("es-MX", "es"), ("fr", "en"), (None, "en"), ("", "en")])
def test_normalize_lang(lang, expected):
    assert R.normalize_lang(lang) == expected
