"""The committed WS2 PR4 filing panel stays well-formed (no PDF is read here)."""
import json

from backend.legislation import filing_evaluation as fe
from backend.legislation.filing_details import FIELD_UNITS
from eval import filing_panel

PANEL = json.loads(filing_panel.PANEL.read_text())


def test_panel_meets_the_size_and_split_minimums():
    rows = PANEL["rows"]
    held = [r for r in rows if r["split"] == "held_out"]
    assert len(rows) >= fe.MIN_PANEL_ROWS and len(held) >= fe.MIN_HELD_OUT_ROWS
    for row in rows:
        moved = "before the split" in row["notes"]
        assert row["split"] == ("train" if moved else filing_panel.split_for(row["record_number"]))


def test_labels_use_known_fields_units_and_sources_and_no_row_claims_verification():
    for row in PANEL["rows"]:
        assert row["label_status"] in {"assistant_draft", "human_verified"}
        assert set(row["attachments"]) == {"ordinance", "narrative"}
        for att in row["attachments"].values():
            assert len(att["sha256"]) == 64 and att["url"].startswith("https://")
            assert "eds" not in att["file_name"].lower() and "application" not in att["file_name"].lower()
        for field_id, label in row["labels"].items():
            assert label["unit"] == FIELD_UNITS[field_id]
            assert label["source"] == ("ordinance" if field_id.endswith("_district") else "narrative")
            assert label["page"] >= 1
        if row["label_status"] == "human_verified":  # a person's name and date, never a bulk flip
            assert row.get("verified_by") and row.get("verified_on")


def test_post_hoc_versions_cannot_report_a_gate():
    assert PANEL["held_out_scored_with"] == "ws2-pr4a-3"
    assert PANEL["held_out_history"][0]["gate"] == "fail"


def test_fresh_historical_panel_is_disjoint_spent_and_well_formed():
    fresh = json.loads(filing_panel.FRESH.read_text())
    assert len(fresh["rows"]) >= fe.MIN_HELD_OUT_ROWS
    assert not {r["record_number"] for r in fresh["rows"]} & {r["record_number"] for r in PANEL["rows"]}
    assert fresh["held_out_scored_with"] == "ws2-pr4a-4" and fresh["held_out_history"][0]["gate"] == "fail"
    for row in fresh["rows"]:
        assert row["split"] == "held_out" and set(row["attachments"]) == {"ordinance", "narrative"}
        for field_id, label in row["labels"].items():
            assert label["unit"] == FIELD_UNITS[field_id]


def test_accruing_set_is_disjoint_unspent_and_sealed_below_ten_rows():
    accruing = json.loads((filing_panel.PANEL.parent / "filing_panel_accruing.json").read_text())
    earlier = {r["record_number"] for r in PANEL["rows"]} | {
        r["record_number"] for r in json.loads(filing_panel.FRESH.read_text())["rows"]}
    assert not {r["record_number"] for r in accruing["rows"]} & earlier
    assert accruing["held_out_scored_with"] is None
    if len(accruing["rows"]) < fe.MIN_HELD_OUT_ROWS:
        assert filing_panel.main(["--fresh-panel", str(filing_panel.PANEL.parent / "filing_panel_accruing.json")]) == 2
