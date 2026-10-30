"""WS1 M6: the AI-read new district of an off-map rezoning ordinance. No model, no network:
the model client, the PDF fetch and the live map lookup are fakes."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from backend.legislation import ordinance_reader as r
from backend.legislation import rezonings
from backend.retrieval import clerk

PINS = [["14283190070000", 41.9, -87.7], ["14283190080000", 41.9, -87.7]]
REPLY = '{"common_address": "6711 S Western Ave", "changes": [{"map_no": "20-G", "from_district": "c2-2", "to_district": "B2-5"}]}'


class FakeModel:
    def __init__(self, text=REPLY, fail=False):
        self.text, self.fail, self.calls = text, fail, 0
        self.messages = SimpleNamespace(create=self._create)

    async def _create(self, **kw):
        self.calls += 1
        if self.fail:
            raise RuntimeError("overloaded")
        assert kw["messages"][0]["content"][0]["type"] == "document"
        return SimpleNamespace(content=[SimpleNamespace(text=self.text)])


def run(coro):
    return asyncio.run(coro)


def lookup_for(*districts):
    it = iter(districts)

    async def lookup(lat, lon):
        d = next(it, None)
        return {"zone_class": d} if d else None
    return lookup


def row(record="O2026-0028350", **over):
    base = {"record": record, "map_status": "off_map", "passed_on": "2026-10-14", "pins": PINS, "parse": {"status": "clean", "segments": []}}
    return {**base, **over}


def matter(record="O2026-0028350"):
    att = clerk.ClerkAttachment(file_name=f"{record}.pdf", url="https://x/y.pdf", type="Legislation")
    return SimpleNamespace(record_number=record, legislation_pdf=lambda: att)


@pytest.fixture(autouse=True)
def fake_pdf(monkeypatch):
    async def fetch(m, client=None):
        return b"%PDF-1.4 fake"
    monkeypatch.setattr(r, "fetch_pdf", fetch)


def test_parse_reply_normalizes_districts():
    out = r.parse_reply("Here: " + REPLY)
    assert out["changes"] == [{"map_no": "20-G", "from_district": "C2-2", "to_district": "B2-5"}]
    assert r.normalize_district("rm-4.5") == "RM-4.5"
    assert r.normalize_district("the B2 district") is None


@pytest.mark.parametrize("text", ["no json", '{"changes": "x"}', "{broken"])
def test_parse_reply_rejects_malformed(text):
    with pytest.raises(r.ReaderUnavailable):
        r.parse_reply(text)


def test_validate_drops_a_from_district_the_map_does_not_show():
    raw = r.parse_reply(REPLY)
    assert r.validate(raw, {"C2-2"})["status"] == "validated"
    assert r.validate(raw, {"B3-2"}) == {"status": "unvalidated", "changes": []}


def test_attach_reads_validates_and_reuses():
    rows = [row()]
    model = FakeModel()
    calls = run(r.attach_readings(rows, {"O2026-0028350": matter()}, None, model_client=model, lookup=lookup_for("C2-2"), pause=0))
    rd = rows[0]["ai_reading"]
    assert calls == 1 and rd["status"] == "validated" and rd["changes"][0]["to_district"] == "B2-5"
    # next day: the stored raw reading is re-validated against the map, no second model call
    rows2 = [row()]
    calls = run(r.attach_readings(rows2, {"O2026-0028350": matter()}, rows, model_client=model, lookup=lookup_for("C2-2"), pause=0))
    assert calls == 0 and model.calls == 1 and rows2[0]["ai_reading"]["status"] == "validated"
    # the map moved on under it: the same reading no longer validates
    rows3 = [row()]
    run(r.attach_readings(rows3, {}, rows2, model_client=model, lookup=lookup_for("B2-5"), pause=0))
    assert rows3[0]["ai_reading"]["status"] == "unvalidated"


def test_model_failure_is_recorded_not_cached_as_no_district():
    rows = [row()]
    run(r.attach_readings(rows, {"O2026-0028350": matter()}, None, model_client=FakeModel(fail=True), lookup=lookup_for("C2-2"), pause=0))
    assert rows[0]["ai_reading"]["status"] == "failed"
    assert not r.reusable(rows[0]["ai_reading"])           # retried next run
    assert r.district_for(rows[0]) is None


def test_skips_on_map_and_unparsed_rows():
    rows = [row(map_status="on_map"), row(record="O2", parse={"status": "partial"}), row(record="O3", pins=[])]
    model = FakeModel()
    assert run(r.attach_readings(rows, {}, None, model_client=model, pause=0)) == 0
    assert model.calls == 0 and all("ai_reading" not in x for x in rows)


def test_district_for_narrows_multi_change_ordinance_by_live_district():
    reading = {"status": "validated", "changes": [
        {"from_district": "C2-2", "to_district": "B2-5"}, {"from_district": "RS-3", "to_district": "RT-4"}], "pdf": "u"}
    rw = {"ai_reading": reading}
    assert r.district_for(rw) is None                      # ambiguous without the parcel's district
    assert r.district_for(rw, "rs-3")["to_district"] == "RT-4"
    assert r.district_for(rw, "B3-1") is None              # this parcel's district isn't in the ordinance


def test_agreement_log_counts_agree_and_disagree_once_each():
    prev = [row("A", ai_reading={"status": "validated", "changes": [{"from_district": "C2-2", "to_district": "B2-5"}]}),
            row("B", ai_reading={"status": "validated", "changes": [{"from_district": "C2-2", "to_district": "B2-5"}]}),
            row("C", ai_reading={"status": "validated", "changes": [{"from_district": "C2-2", "to_district": "B2-5"}]})]
    now = [row("A", map_status="on_map"), row("B", map_status="on_map"), row("C", map_status="on_map")]
    log = r.agreement_update(prev, now, {"A": {"B2-5"}, "B": {"B3-5"}}, None)   # C: map not seen → neither
    assert r.agreement_counts(log) == {"n": 2, "agree": 1}
    assert r.agreement_update(prev, now, {"A": {"B2-5"}}, log) == log


def test_matches_for_carries_a_validated_district_only(tmp_path):
    ai = {"status": "validated", "changes": [{"from_district": "C2-2", "to_district": "B2-5"}], "pdf": "u"}
    snap = {"status": "ok", "checked_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
            "rezoning_check": {"agreement": {"n": 3, "agree": 3}},
            "rezonings": [{**row(), "url": "u", "title": "t", "parse": {"status": "clean", "segments": [], "maps": None}, "ai_reading": ai}]}
    from backend.legislation import currency
    if currency.check_state(snap) == "unknown":
        pytest.skip("snapshot freshness helper changed")
    hit = rezonings.matches_for("14283190070000", None, None, snap, live_district="C2-2")[0]
    assert (hit["from_district"], hit["to_district"], hit["agreement"]) == ("C2-2", "B2-5", {"n": 3, "agree": 3})
    assert "to_district" not in rezonings.matches_for("14283190070000", None, None, snap, live_district="B3-1")[0]


def test_sync_part_is_dormant_without_the_flag_and_key(monkeypatch):
    from backend.legislation import sync
    from backend.config import get_settings

    s = get_settings()
    monkeypatch.setattr(s, "ordinance_reader_enabled", False)
    out = run(sync._reader_part([row()], [matter()], [], {"agreement_log": [{"record": "X", "agree": True}]}))
    assert out["reader"] == "off" and out["agreement"] == {"n": 1, "agree": 1}

    monkeypatch.setattr(s, "ordinance_reader_enabled", True)
    monkeypatch.setattr(s, "anthropic_api_key", "")
    assert run(sync._reader_part([row()], [matter()], [], {}))["reader"] == "off"


def test_recorded_readings_of_30_on_map_ordinances_agree_with_the_map():
    """The backtest (WS1 M6): readings of 30 ordinances that are already on the City map, taken from their
    PDFs (by Claude in-session, not the production model), run through the production normalizer and
    validator, must name the district the map's polygon shows. Gate: >= 95%."""
    import json
    from pathlib import Path

    doc = json.loads((Path(__file__).parent / "fixtures/ordinances/readings_on_map.json").read_text())
    agree = 0
    for o in doc["ordinances"]:
        changes = [{"map_no": c["map_no"], "from_district": r.normalize_district(c["from_district"]),
                    "to_district": r.normalize_district(c["to_district"])} for c in o["changes"]]
        assert all(c["from_district"] and c["to_district"] for c in changes), o["record"]   # every district parses
        agree += bool({c["to_district"] for c in changes} & set(o["map_districts"]))
    assert len(doc["ordinances"]) == 30 and agree / len(doc["ordinances"]) >= 0.95
    assert agree == 30


def test_ordinance_spellings_normalize():
    assert [r.normalize_district(x) for x in ("RT4", "RM 4.5", "RM- 4.5", "Rt-4", "B2-1.5", "DX-3")] == \
        ["RT-4", "RM-4.5", "RM-4.5", "RT-4", "B2-1.5", "DX-3"]


def test_a_no_change_ordinance_shows_no_district():
    rw = {"ai_reading": {"status": "validated", "changes": [{"from_district": "RT-4", "to_district": "RT-4"}]}}
    assert r.district_for(rw) is None
