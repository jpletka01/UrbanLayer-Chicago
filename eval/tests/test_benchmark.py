"""The published benchmark page must match the committed results and stay honest."""


from eval import benchmark as b


def test_committed_page_is_current():
    md, js = b.build()
    assert (b.OUT_DIR / "README.md").read_text() == md, "run `make benchmark`"
    assert (b.OUT_DIR / "results.json").read_text() == js, "run `make benchmark`"


def test_page_states_limits_and_failures():
    md, _ = b.build()
    assert "## 6. Limits" in md
    assert "not yet reviewed" in md
    assert "Starting point" in md  # the failing first run stays on the page
    assert "P2, P5" in md


def test_current_results_cover_both_surfaces_and_say_how_many_parcels():
    data = b.collect()
    assert set(data["current"]) == {"profile", "chat"}
    total = len(data["parcels"])
    assert data["current"]["profile"]["aggregate"]["parcels_scored"] == total  # the Profile is free, so it is always run on every parcel
    assert 7 <= data["current"]["chat"]["aggregate"]["parcels_scored"] <= total  # chat costs credits: the page says how many ran
    for surf in data["current"].values():
        assert surf["key"] == data["kit_version"]  # never shown under an older key: such runs are re-scored


def test_baseline_row_reproduces_recorded_numbers():
    first = b.collect()["progression"][0]["surfaces"]
    assert first["profile"]["points"] == 51 and first["profile"]["confident_wrong"] == 2
    assert first["chat"]["points"] == 38 and first["chat"]["confident_wrong"] == 7


def test_no_private_research_leaks():
    md, js = b.build()
    for text in (md, js):
        assert "research/" not in text


def test_review_pending_is_stated_and_reviewed_flips_the_page(monkeypatch, tmp_path):
    md, _ = b.build()
    assert "Outside review: pending" in md and "not yet reviewed" in md
    rv = {"status": "reviewed", "reviewer": {"role": "a zoning attorney", "credentials": "Chicago bar, 10 yrs", "name_published": False,
                                             "date": "2026-11-01", "scope": "judgment fields"},
          "fields": {"P2.F": {"verdict": "agree"}, "P3.E": {"verdict": "disagree", "note": "dash-2 does allow X"}}}
    f = tmp_path / "review.json"
    f.write_text(__import__("json").dumps(rv))
    monkeypatch.setattr(b, "REVIEW_FILE", f)
    md, js = b.build()
    assert "1 agreed, 1 disagreed" in md and "dash-2 does allow X" in md  # disagreements are published
    assert "not yet reviewed" not in md
    assert __import__("json").loads(js)["review"]["agree"] == 1
