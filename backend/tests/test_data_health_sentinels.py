"""WS6 M4: the daily sentinels, and the F8 replay (the check that would have caught 2026-10-02's landmark misread)."""

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from backend.data_health import probes
from backend.data_health.evaluate import ProbeError, evaluate
from backend.data_health.registry import BY_ID
from backend.data_health.sentinels import (
    KEY_TO_LAYER_TYPE, LANDMARK_TYPES, UNCURATED_EXTRA, Sentinel, compare, load_sentinels, overlay_types, run_sentinels,
)
from backend.retrieval.regulatory.overlays import OVERLAY_LAYERS

REPO = Path(__file__).resolve().parents[2]
FX = Path(__file__).parent / "fixtures" / "data_health"
KIT = REPO / "eval" / "kit" / "parcels.json"
LIVE_TYPES = {lid: m["type"] for lid, m in OVERLAY_LAYERS.items()}
# Production's layer mapping on 2026-10-02, before F8's fix: layer 7 (the CHRS survey) read as "landmark building".
PRE_F8_TYPES = {**LIVE_TYPES, 7: "landmark_building"}


def sentinel(id_="P11") -> Sentinel:
    return {s.id: s for s in load_sentinels()}[id_]


# --- in sync with the kit --------------------------------------------------------------------------------

def test_sentinels_stay_in_sync_with_the_kit_key():
    """eval/ is not in the image, so the sentinels are generated from the key and committed. If the key moves
    (a re-key, a new parcel), regenerate: python -m backend.data_health.sentinels --from-kit eval/kit/parcels.json --control ..."""
    kit = json.loads(KIT.read_text())
    ours = {s.id: s for s in load_sentinels() if not s.control}
    assert set(ours) == {p["id"] for p in kit["parcels"]}
    for p in kit["parcels"]:
        s = ours[p["id"]]
        assert s.address == p["address"], p["id"]
        assert s.district == p["A"]["district"], p["id"]
        assert set(s.overlays) == {KEY_TO_LAYER_TYPE[e] for e in p["D"]["expected"]}, p["id"]
        if p.get("pin"):
            assert s.pin == p["pin"], p["id"]


def test_there_is_a_positive_control_that_is_a_designated_landmark():
    controls = [s for s in load_sentinels() if s.control]
    assert len(controls) == 1
    c = controls[0]
    assert "landmark_building" in c.overlays and c.district and "tdab-kixi" in c.basis


def test_every_sentinel_point_is_in_chicago():
    for s in load_sentinels():
        assert 41.6 < s.lat < 42.1 and -87.95 < s.lon < -87.5, s.id


def test_sentinels_are_a_registry_source_with_a_probe():
    spec = BY_ID["internal.sentinels"]
    assert spec.probe == "sentinels" and spec.severity == "critical" and "sentinels" in probes.PROBES


# --- comparing ---------------------------------------------------------------------------------------------

def test_a_matching_parcel_is_clean_and_whitespace_in_the_district_is_ignored():
    s = sentinel("P4")  # "PD 835"
    assert compare(s, "PD  835 ", set(s.overlays)) == []


def test_a_wrong_district_is_an_alarm():
    s = sentinel("P7")  # RT-4, rezoned from M1-2 in June
    f = compare(s, "M1-2", set(s.overlays))
    assert len(f) == 1 and f[0].level == "alarm" and "district is M1-2, key says RT-4" in f[0].text


def test_an_unexpected_or_missing_overlay_is_an_alarm():
    s = sentinel("P5")
    got = (set(s.overlays) - {"ssa"}) | {"pmd_subarea"}
    texts = [f.text for f in compare(s, s.district, got)]
    assert any("pmd_subarea found, not in the key" in t for t in texts) and any("ssa not found" in t for t in texts)


def test_overlay_types_the_key_does_not_curate_are_not_a_mismatch_but_a_missing_key_overlay_still_is():
    s = sentinel("P2")
    assert compare(s, s.district, set(s.overlays) | UNCURATED_EXTRA) == []
    p6 = sentinel("P6")  # the key lists the ADU zone here
    assert "adu_area" in p6.overlays and compare(p6, p6.district, set(p6.overlays) - {"adu_area"})


def test_the_control_alarms_when_its_landmark_stops_being_found():
    c = [s for s in load_sentinels() if s.control][0]
    f = compare(c, c.district, set(c.overlays) - {"landmark_building"})
    assert any("landmark_building not found" in x.text for x in f)


# --- F8 replay --------------------------------------------------------------------------------------------

def _layer7_hit():
    rec = json.loads((FX / "p11_layer7_hit.json").read_text())
    return rec["attributes"][0]


def test_f8_replay_the_pre_fix_mapping_would_have_alarmed_on_p11():
    """2026-10-02: the code read layer 7 (the survey's orange/red buildings) as "landmark building", so P11 came
    back a Chicago Landmark. The sentinel derives the overlay set the way production did, finds a landmark the
    key says is not there, and alarms. With today's mapping (layer 7 not queried) the same hits are clean."""
    p11 = sentinel("P11")
    assert "landmark_building" not in p11.overlays
    base_hits = [(3, {}), (8, {}), (7, _layer7_hit())]            # lakefront, national register, the survey layer
    # the key's overlays besides ARO (ARO is layer 20, kept out of the replay's synthetic hits)
    pre = overlay_types(base_hits + [(20, {})], PRE_F8_TYPES)
    assert "landmark_building" in pre
    findings = compare(p11, p11.district, pre)
    assert len(findings) == 1 and findings[0].level == "alarm"
    assert "landmark_building found, not in the key" in findings[0].text and "F8" in findings[0].text
    # the fixed mapping derives the key's set exactly
    now = overlay_types(base_hits + [(20, {})], LIVE_TYPES)
    assert now == set(p11.overlays) and compare(p11, p11.district, now) == []


def test_the_recorded_layer7_hit_is_the_survey_not_a_designation():
    assert _layer7_hit()["COLOR_ID"] == 1                          # orange survey rating
    assert 7 not in OVERLAY_LAYERS and LANDMARK_TYPES == {"landmark_building", "historic_district"}


# --- running them ------------------------------------------------------------------------------------------

def _fake_world(sentinels, *, wrong_district=(), failed_layers=(), boom=()):
    by_pt = {(s.lat, s.lon): s for s in sentinels}
    inv = {v: k for k, v in LIVE_TYPES.items()}

    async def lookup(lat, lon):
        s = by_pt[(lat, lon)]
        if s.id in boom:
            raise RuntimeError("503")
        return {"zone_class": "XX-1" if s.id in wrong_district else s.district}

    async def overlays(lat, lon):
        s = by_pt[(lat, lon)]
        return SimpleNamespace(hits=[(inv[t], {}) for t in s.overlays], failed=[17] if s.id in failed_layers else [])

    return lookup, overlays


def test_all_green():
    ss = load_sentinels()
    lookup, overlays = _fake_world(ss)
    run = asyncio.run(run_sentinels(ss, lookup=lookup, overlays=overlays))
    assert (run.green, run.checked, run.findings, run.unchecked) == (13, 13, [], [])


def test_a_wrong_district_and_a_failed_lookup_are_reported_apart():
    ss = load_sentinels()
    lookup, overlays = _fake_world(ss, wrong_district={"P3"}, boom={"P8"}, failed_layers={"P1"})
    run = asyncio.run(run_sentinels(ss, lookup=lookup, overlays=overlays))
    assert [f.text.split(":")[0] for f in run.findings] == ["P3 1500 W Wilson Ave"]
    assert run.green == 10 and run.checked == 12                    # P8 could not be asked; P1 had a layer down
    assert any(u.startswith("P8") for u in run.unchecked) and any(u.startswith("P1 ") for u in run.unchecked)


def test_an_overlay_layer_that_could_not_be_read_never_counts_as_the_overlay_being_absent():
    ss = [sentinel("P6")]
    lookup, overlays = _fake_world(ss, failed_layers={"P6"})
    async def partial(lat, lon):
        return SimpleNamespace(hits=[], failed=[17])               # no hits at all, because a layer is down
    run = asyncio.run(run_sentinels(ss, lookup=lookup, overlays=partial))
    assert run.findings == [] and run.green == 0 and run.unchecked      # the district was fine; overlays unknown


def test_the_probe_alarms_on_a_mismatch_warns_on_unchecked_and_errs_when_nothing_could_be_checked(monkeypatch):
    ss = load_sentinels()
    lookup, overlays = _fake_world(ss, wrong_district={"P3"}, boom={"P8"})

    async def fake_run(sentinels, **kw):
        return await run_sentinels(sentinels, lookup=lookup, overlays=overlays)

    monkeypatch.setattr("backend.data_health.sentinels.run_sentinels", fake_run)
    res = asyncio.run(probes.probe_sentinels(BY_ID["internal.sentinels"], None))
    levels = sorted({f.level for f in res.findings})
    assert levels == ["alarm", "warn"] and "11 of 13" in res.info
    from datetime import date
    s = evaluate(BY_ID["internal.sentinels"], res, date(2026, 10, 22))
    assert s.state == "alarm" and "key says" in s.reason

    lookup2, overlays2 = _fake_world(ss, boom={s.id for s in ss})

    async def all_down(sentinels, **kw):
        return await run_sentinels(sentinels, lookup=lookup2, overlays=overlays2)

    monkeypatch.setattr("backend.data_health.sentinels.run_sentinels", all_down)
    with pytest.raises(ProbeError) as e:
        asyncio.run(probes.probe_sentinels(BY_ID["internal.sentinels"], None))
    assert e.value.kind == "transient"


def test_green_sentinels_make_the_source_ok(monkeypatch):
    ss = load_sentinels()
    lookup, overlays = _fake_world(ss)

    async def fake_run(sentinels, **kw):
        return await run_sentinels(sentinels, lookup=lookup, overlays=overlays)

    monkeypatch.setattr("backend.data_health.sentinels.run_sentinels", fake_run)
    res = asyncio.run(probes.probe_sentinels(BY_ID["internal.sentinels"], None))
    from datetime import date
    s = evaluate(BY_ID["internal.sentinels"], res, date(2026, 10, 22))
    assert s.state == "ok" and "13 of 13" in s.reason
