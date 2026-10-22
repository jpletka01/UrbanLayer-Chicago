"""WS6 M5: the warn-only artifact-age check, the probes it adds, and the workflows that run them."""

import asyncio
import json
from datetime import date
from pathlib import Path

import httpx
import yaml

from backend.data_health import artifacts, probes
from backend.data_health.evaluate import evaluate
from backend.data_health.registry import BY_ID

REPO = Path(__file__).resolve().parents[2]
TODAY = date(2026, 10, 22)


def _repo(tmp_path: Path, *, code="2026-10-01", cache_built=1781772453, cache_vintage="2026-10-01", transit="2026-09-01",
          key="2026-10-21.1", bench="2026-10-21") -> Path:
    def write(rel, data):
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(data))

    write("backend/code_vintage.json", {"current_through": code})
    meta = {"built_at": cache_built, **({"code_vintage": cache_vintage} if cache_vintage else {})}
    write("ingestion/data/zoning_cache.json", {"_meta": meta, "entries": {}})
    if transit:
        write("ingestion/data/transit_stations.meta.json", {"built_at": transit})
    write("eval/kit/parcels.json", {"version": key})
    write("docs/benchmark/results.json", {"current": {"profile": {"date": bench}, "chat": {"date": "2026-08-01"}}})
    return tmp_path


def by_name(checks):
    return {c.name: c for c in checks}


def test_everything_current_is_quiet(tmp_path):
    c = by_name([f(date(2026, 10, 22), _repo(tmp_path, cache_built=1792000000, cache_vintage="2026-10-01")) for f in
                 (artifacts.check_code_vintage, artifacts.check_zoning_cache, artifacts.check_transit,
                  artifacts.check_kit_key, artifacts.check_benchmark)] )
    assert {n: x.state for n, x in c.items()} == {
        "code text vintage": "ok", "zoning cache": "ok", "transit stations": "ok", "answer key": "ok", "benchmark": "ok"}
    assert not any(x.annotates for x in c.values())


def test_the_code_text_warns_after_60_days_and_alarms_after_90(tmp_path):
    r = _repo(tmp_path, code="2026-08-20")                 # 63 days
    assert artifacts.check_code_vintage(TODAY, r).state == "warn"
    r = _repo(tmp_path, code="2026-06-17")                 # 127 days
    c = artifacts.check_code_vintage(TODAY, r)
    assert c.state == "alarm" and c.age_days == 127 and "alarm after 90" in c.message


def test_the_registry_ack_is_named_so_a_pr_author_is_not_left_guessing(tmp_path):
    c = artifacts.check_code_vintage(date(2026, 11, 1), _repo(tmp_path, code="2026-06-17"))
    assert "acked in the data-health registry until 2026-12-15" in c.message
    after = artifacts.check_code_vintage(date(2027, 1, 5), _repo(tmp_path, code="2026-06-17"))
    assert "acked" not in after.message


def test_the_zoning_cache_must_record_the_code_vintage_it_was_checked_against(tmp_path):
    assert artifacts.check_zoning_cache(TODAY, _repo(tmp_path, cache_vintage=None)).state == "warn"
    c = artifacts.check_zoning_cache(TODAY, _repo(tmp_path, cache_vintage="2026-03-18"))
    assert c.state == "alarm" and "2026-03-18" in c.message and "2026-10-01" in c.message
    assert artifacts.check_zoning_cache(TODAY, _repo(tmp_path, cache_vintage="2026-10-01")).state == "ok"


def test_transit_needs_its_sidecar_and_is_judged_on_its_build_date(tmp_path):
    assert artifacts.check_transit(TODAY, _repo(tmp_path, transit=None)).state == "warn"
    assert artifacts.check_transit(TODAY, _repo(tmp_path, transit="2026-03-01")).state == "warn"    # 235 days
    assert artifacts.check_transit(TODAY, _repo(tmp_path, transit="2025-09-01")).state == "alarm"   # over a year


def test_the_answer_key_and_the_benchmark_have_their_own_tolerances(tmp_path):
    assert artifacts.check_kit_key(TODAY, _repo(tmp_path, key="2026-03-01.1")).state == "warn"
    assert artifacts.check_kit_key(TODAY, _repo(tmp_path, key="draft")).state == "warn"            # undated: said, not skipped
    assert artifacts.check_benchmark(TODAY, _repo(tmp_path, bench="2026-08-01")).state == "warn"   # 82 days > 45


def test_the_real_repo_has_a_sidecar_a_zoning_vintage_and_a_current_key():
    c = by_name(artifacts.run_checks(TODAY))
    assert c["transit stations"].state == "ok" and c["zoning cache"].state == "ok"
    assert c["hand table"].state == "ok" and c["answer key"].state == "ok"


def test_ci_mode_only_ever_annotates_warnings_and_always_exits_zero(capsys, monkeypatch, tmp_path):
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    assert artifacts.main(["--ci", "--today", "2026-12-01"]) == 0
    out = capsys.readouterr().out
    assert "::warning file=backend/code_vintage.json" in out and "::error" not in out
    assert "| Artifact | State | Detail |" in summary.read_text()
    # outside CI a red artifact is a nonzero exit, so a person running it by hand sees it
    assert artifacts.main(["--today", "2026-12-01"]) == 1


def test_a_stale_artifact_never_turns_the_ci_step_red():
    ci = yaml.safe_load((REPO / ".github/workflows/ci.yml").read_text())
    step = next(s for s in ci["jobs"]["test"]["steps"] if "artifacts" in s.get("run", ""))
    assert step["continue-on-error"] is True and step["run"].endswith("--ci")
    assert ci["jobs"]["deploy"]["needs"] == "test" or "test" in ci["jobs"]["deploy"]["needs"]


# --- the transit sidecar is shipped everywhere the artifact is ------------------------------------------

def test_the_sidecar_is_allowlisted_in_gitignore_dockerignore_and_dockerfile():
    for rel in (".gitignore", ".dockerignore", "backend/Dockerfile"):
        assert "transit_stations.meta.json" in (REPO / rel).read_text(), rel
    assert (REPO / "ingestion/data/transit_stations.meta.json").exists()


def test_the_zoning_cache_builder_writes_the_code_vintage():
    src = (REPO / "backend/zoning_cache_build.py").read_text()
    assert '"code_vintage"' in src and "get_code_vintage_record" in src


# --- probes ---------------------------------------------------------------------------------------------

def _runs(*specs):
    return {"workflow_runs": [{"status": "completed", "conclusion": c, "updated_at": f"{d}T10:30:00Z",
                               "html_url": f"https://github.com/x/actions/runs/{i}"} for i, (c, d) in enumerate(specs)]}


def test_parse_workflow_runs():
    assert probes.parse_workflow_runs(_runs(("success", "2026-10-19"), ("failure", "2026-10-12"))) == (
        date(2026, 10, 19), "success", "https://github.com/x/actions/runs/0")
    ok_day, concl, url = probes.parse_workflow_runs(_runs(("failure", "2026-10-26"), ("success", "2026-10-19")))
    assert ok_day == date(2026, 10, 19) and concl == "failure" and url.endswith("/0")
    assert probes.parse_workflow_runs({"workflow_runs": []}) == (None, None, None)
    assert probes.parse_workflow_runs({"workflow_runs": [{"status": "in_progress"}]}) == (None, None, None)


def _probe(spec, handler):
    async def go():
        client, _ = probes.make_client(httpx.MockTransport(handler))
        ctx = probes.ProbeContext(client=client, sem=asyncio.Semaphore(2), today=TODAY)
        try:
            return await probes.run_probe(spec, ctx)
        finally:
            await client.aclose()

    return asyncio.run(go())


def test_the_weekly_kit_source_is_green_when_a_recent_run_passed():
    spec = BY_ID["eval.kit_weekly"]
    res = _probe(spec, lambda r: httpx.Response(200, json=_runs(("success", "2026-10-19"))))
    assert res.content == date(2026, 10, 19) and not res.findings
    assert evaluate(spec, res, TODAY).state == "ok"


def test_the_weekly_kit_source_warns_at_nine_days_and_alarms_at_sixteen():
    spec = BY_ID["eval.kit_weekly"]
    old = lambda d: _probe(spec, lambda r: httpx.Response(200, json=_runs(("success", d))))   # noqa: E731
    assert evaluate(spec, old("2026-10-12"), TODAY).state == "warn"      # 10 days
    assert evaluate(spec, old("2026-10-05"), TODAY).state == "alarm"     # 17 days


def test_a_failed_latest_run_alarms_at_once_even_if_the_last_success_is_recent():
    spec = BY_ID["eval.kit_weekly"]
    res = _probe(spec, lambda r: httpx.Response(200, json=_runs(("failure", "2026-10-21"), ("success", "2026-10-14"))))
    s = evaluate(spec, res, TODAY)
    assert s.state == "alarm" and "ended failure" in s.reason


def test_before_the_first_run_is_unknown_never_red():
    spec = BY_ID["eval.kit_weekly"]
    not_yet = _probe(spec, lambda r: httpx.Response(404, json={"message": "Not Found"}))
    assert evaluate(spec, not_yet, TODAY).state == "unknown"
    empty = _probe(spec, lambda r: httpx.Response(200, json={"workflow_runs": []}))
    assert evaluate(spec, empty, TODAY).state == "unknown"


def test_a_github_rate_limit_is_a_transient_probe_error_not_a_failed_kit():
    res = _probe(BY_ID["eval.kit_weekly"], lambda r: httpx.Response(403, json={"message": "API rate limit exceeded"}))
    assert res.error and res.error.kind == "transient"


def test_the_transit_probe_dates_the_artifact_by_its_sidecar():
    spec = BY_ID["artifact.transit_stations"]
    res = _probe(spec, lambda r: httpx.Response(200, headers={"Last-Modified": "Mon, 14 Sep 2026 12:00:00 GMT"}))
    assert res.content == date(2026, 6, 1) and "CTA feed was last modified 2026-09-14" in res.info
    assert evaluate(spec, res, TODAY).state == "ok"
    assert evaluate(spec, res, date(2027, 1, 1)).state == "warn"          # 214 days > 180


# --- the workflow --------------------------------------------------------------------------------------

def test_the_weekly_workflow_is_scheduled_dispatchable_and_free():
    wf = yaml.safe_load((REPO / ".github/workflows/kit-weekly.yml").read_text())
    on = wf.get("on") or wf[True]                                        # YAML reads a bare `on` as True
    assert on["schedule"] == [{"cron": "0 10 * * 1"}]
    assert on["workflow_dispatch"]["inputs"]["inject_mismatch"]["type"] == "boolean"
    assert wf["permissions"] == {"contents": "read"}
    text = (REPO / ".github/workflows/kit-weekly.yml").read_text()
    assert "--surfaces profile" in text and "ANTHROPIC" not in text and "--surfaces profile,chat" not in text
    assert "retention-days: 90" in text and "eval.kit_gate" in text and "--inject-mismatch" in text


def test_every_action_the_new_workflow_uses_is_one_the_repo_already_pins():
    pinned = set()
    for f in (REPO / ".github/workflows").glob("*.yml"):
        if f.name != "kit-weekly.yml":
            pinned |= {w for w in f.read_text().split() if w.startswith("actions/")}
    used = {w for w in (REPO / ".github/workflows/kit-weekly.yml").read_text().split() if w.startswith("actions/")}
    assert used - pinned <= {"actions/upload-artifact@v7"}, used - pinned
