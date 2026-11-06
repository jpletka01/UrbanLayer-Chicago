from backend.legislation.filing_evaluation import FieldValue, evaluate, panel_passes


def test_omissions_reduce_recall_and_cannot_pass_by_silence():
    score = evaluate({"units": FieldValue("10", 2)}, {})
    assert score.precision == 0 and score.recall == 0 and not score.passes


def test_wrong_page_or_unit_blocks_even_when_value_matches():
    expected = {"height": FieldValue("45", 3, "ft")}
    wrong_page = evaluate(expected, {"height": FieldValue("45", 4, "ft")})
    wrong_unit = evaluate(expected, {"height": FieldValue("45", 3, "stories")})
    assert wrong_page.wrong_page == 1 and not wrong_page.passes
    assert wrong_unit.wrong_unit == 1 and not wrong_unit.passes


def test_panel_requires_30_rows_and_held_out_split():
    good = evaluate({"units": FieldValue("10", 2)}, {"units": FieldValue("10", 2)})
    assert not panel_passes([good], panel_size=29, held_out_size=10)
    assert not panel_passes([good], panel_size=30, held_out_size=9)
    assert panel_passes([good], panel_size=30, held_out_size=10)
