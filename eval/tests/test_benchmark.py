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


def test_current_results_cover_all_parcels_and_both_surfaces():
    data = b.collect()
    assert set(data["current"]) == {"profile", "chat"}
    for s in data["current"].values():
        assert s["aggregate"]["parcels_scored"] == 7


def test_baseline_row_reproduces_recorded_numbers():
    first = b.collect()["progression"][0]["surfaces"]
    assert first["profile"]["points"] == 51 and first["profile"]["confident_wrong"] == 2
    assert first["chat"]["points"] == 38 and first["chat"]["confident_wrong"] == 7


def test_no_private_research_leaks():
    md, js = b.build()
    for text in (md, js):
        assert "research/" not in text
