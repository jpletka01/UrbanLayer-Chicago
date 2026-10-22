from eval.designation_backtest import _bucket, report


def test_age_buckets_cover_every_age_once():
    assert [_bucket(a) for a in (0, 29, 30, 89, 90, 179, 180, 399, 450)] == [
        "0-30 days", "0-30 days", "30-90 days", "30-90 days", "90-180 days", "90-180 days", "180-400 days", "180-400 days", "400+ days",
    ]


def test_the_report_names_the_gates_and_what_the_map_shows_by_age():
    res = {
        "since": "2025-09-17", "designations": 2, "clean": 1, "parse_rate": 0.5, "unparsed": ["O1"], "wrong_street": 0, "street_checked": 4,
        "with_parcels": 1, "no_parcels": [], "on_map_by_age": {"0-30 days": {"district": {"tested": 12, "on_map": 1}}},
        "records": [{"record": "O2", "age_days": 29, "kind": "district", "status": "clean", "pins": 13, "tested": 12, "on_map": 1, "name": "Bryn Mawr Avenue District"}],
    }
    text = report(res)
    assert "wrong street: 0 of 4" in text and "district: 1 of 12 (8%)" in text and "Bryn Mawr Avenue District" in text
