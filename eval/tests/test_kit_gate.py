"""WS6 M5: the weekly kit gate: field A is 2, no confident-wrong claim, nothing below the accepted run."""

import json
from pathlib import Path

import pytest

from eval import kit_gate as g

REPO = Path(__file__).resolve().parents[2]


def report(**cells):
    """{parcel: {field: (score, cw)}} -> the slice of parcel_kit.json the gate reads."""
    fields = {p: {f: {"score": s, "cw": cw} for f, (s, cw) in fs.items()} for p, fs in cells.items()}
    return {"surfaces": {"profile": {"fields": fields, "aggregate": {"points": 1, "possible": 2, "answered": 1,
                                                                  "scored_fields": 2, "cw": 0, "a_correct": 1, "parcels": 1}}},
            "meta": {"key_version": "k", "date": "2026-10-22"}}


GOOD = {"P1": {"A": (2, False), "B": (2, False), "C": (1, False), "F": (None, False)}}


def test_a_clean_run_passes():
    cur = g.cells(report(**GOOD))
    assert g.judge(cur, {"P1": {"A": 2, "B": 2, "C": 1, "F": None}}) == ([], [])


def test_a_district_that_is_not_2_fails_even_with_no_accepted_file():
    bad = {"P1": {**GOOD["P1"], "A": (1, False)}}
    failures, _ = g.judge(g.cells(report(**bad)), None)
    assert failures == ["P1 field A (the district) scored 1, must be 2"]
    missing = {"P1": {**GOOD["P1"], "A": (None, False)}}
    assert g.judge(g.cells(report(**missing)), None)[0]


def test_a_confident_wrong_claim_fails():
    cw = {"P1": {**GOOD["P1"], "B": (0, True)}}
    failures, _ = g.judge(g.cells(report(**cw)), None)
    assert "P1 field B is a confident-wrong claim" in failures


def test_a_cell_that_falls_below_the_accepted_run_fails_and_a_rise_is_reported():
    accepted = {"P1": {"A": 2, "B": 2, "C": 1, "F": None}}
    fell = {"P1": {"A": (2, False), "B": (1, False), "C": (2, False), "F": (None, False)}}
    failures, better = g.judge(g.cells(report(**fell)), accepted)
    assert failures == ["P1 field B fell from 2 to 1"] and better == ["P1 field C rose from 1 to 2"]


def test_silence_ranks_between_wrong_and_half_right():
    acc = {"P1": {"A": 2, "B": 1, "C": 0, "F": None}}
    cur = {"P1": {"A": (2, False), "B": (None, False), "C": (None, False), "F": (0, False)}}
    failures, better = g.judge(g.cells(report(**cur)), acc)
    assert any("field B fell from 1 to None" in f for f in failures)            # a claim became silence
    assert any("field F fell from None to 0" in f for f in failures)            # silence became a wrong claim
    assert better == ["P1 field C rose from 0 to None"]


def test_a_parcel_or_field_the_accepted_run_does_not_have_is_not_a_regression():
    cur = g.cells(report(P1=GOOD["P1"], P2={"A": (2, False)}))
    assert g.judge(cur, {"P1": {"A": 2, "B": 2, "C": 1, "F": None}})[0] == []


def test_the_drill_corrupts_a_copy_and_must_fail_without_touching_the_input():
    cur = g.cells(report(**GOOD))
    drilled = g.inject_mismatch(cur)
    assert cur["P1"]["A"] == {"score": 2, "cw": False}                          # the input is untouched
    failures, _ = g.judge(drilled, {"P1": {"A": 2, "B": 2, "C": 1, "F": None}})
    assert len(failures) == 3                                                    # A not 2, CW, fell from 2 to 0


def test_cli_exit_codes_and_the_accepted_round_trip(tmp_path, capsys):
    rep = tmp_path / "parcel_kit.json"
    rep.write_text(json.dumps(report(**GOOD)))
    acc = tmp_path / "accepted.json"
    assert g.main([str(rep), "--accepted", str(acc), "--update-accepted"]) == 0
    assert json.loads(acc.read_text())["scores"] == {"P1": {"A": 2, "B": 2, "C": 1, "F": None}}
    assert g.main([str(rep), "--accepted", str(acc)]) == 0
    assert g.main([str(rep), "--accepted", str(acc), "--inject-mismatch"]) == 1
    assert "meant to fail" in capsys.readouterr().out


def test_a_report_without_the_profile_surface_is_refused(tmp_path):
    rep = tmp_path / "r.json"
    rep.write_text(json.dumps({"surfaces": {"chat": {"fields": {}}}}))
    with pytest.raises(SystemExit):
        g.main([str(rep)])


def test_sentry_is_skipped_without_a_dsn(capsys, monkeypatch):
    monkeypatch.delenv("SENTRY_DSN", raising=False)
    g._sentry(["x"])
    assert "no SENTRY_DSN" in capsys.readouterr().out


def test_the_committed_accepted_run_covers_every_kit_parcel_and_passes_its_own_gate():
    key = json.loads((REPO / "eval/kit/parcels.json").read_text())
    acc = json.loads((REPO / "eval/kit/accepted_profile.json").read_text())
    assert set(acc["scores"]) == {p["id"] for p in key["parcels"]}
    assert all(f["A"] == 2 for f in acc["scores"].values())
    current = {p: {f: {"score": s, "cw": False} for f, s in fs.items()} for p, fs in acc["scores"].items()}
    assert g.judge(current, acc["scores"]) == ([], [])
