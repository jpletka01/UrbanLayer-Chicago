"""Publish the parcel-kit benchmark: docs/benchmark/README.md + results.json.

Everything in the published page is generated from committed result files (the answer
key, the recorded runs, the dated kit reports), so the numbers cannot drift from the
data. UrbanLayer only for now: other tools are added after review and a terms check.

    PYTHONPATH=. python -m eval.benchmark            # rewrite docs/benchmark/
    PYTHONPATH=. python -m eval.benchmark --check    # fail if the committed page is stale
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from eval import parcel_kit as k

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "docs" / "benchmark"
RESULTS = ROOT / "eval" / "results"
BASELINE_DIR = ROOT / "eval" / "kit" / "baseline" / "2026-10-01"

# The runs the page publishes, in order. Each is a dated run of the real system on one
# code version; "profile"/"chat" name the surfaces that run measured. The newest run
# that measured a surface is that surface's CURRENT result.
PROGRESSION = [
    {"id": "baseline", "label": "Starting point (recorded 2026-10-01, hand-scored B/E/F)", "replay": True, "surfaces": ["profile", "chat"]},
    {"id": "2026-10-01-f1", "label": "Chat resolves a typed address to its parcel (F1)", "dir": "2026-10-01-f1", "surfaces": ["chat"]},
    {"id": "2026-10-02-f2", "label": "No false transit 'density bonus' claim (F2)", "dir": "2026-10-02-f2", "surfaces": ["profile", "chat"]},
    {"id": "2026-10-02-f3", "label": "The binding number: lot area per unit + unit yield (F3)", "dir": "2026-10-02-f3", "surfaces": ["profile", "chat"]},
    {"id": "2026-10-02-f5a", "label": "When the district last changed, and how current the code is (F5a)", "dir": "2026-10-02-f5a", "surfaces": ["profile", "chat"]},
    {"id": "2026-10-02-f7", "label": "Overlays named, with what they require (F7)", "dir": "2026-10-02-f7", "surfaces": ["profile"]},
    {"id": "2026-10-02-v4", "label": "Where the page says it stops (V4)", "dir": "2026-10-02-v4", "surfaces": ["profile"]},
]

FIELD_NAMES = {"A": "District", "B": "Use question", "C": "Bulk numbers", "D": "Overlays", "E": "Parking / transit", "F": "Task answer"}


def _pct(x: float) -> str:
    return f"{round(100 * x)}%"


def load_run(entry: dict) -> dict:
    """The scored report for one published run, as the kit's own JSON."""
    key = k.load_key()
    if entry.get("replay"):
        manual = json.loads((BASELINE_DIR / "manual_scores.json").read_text())
        rep = k.score_run_dir(BASELINE_DIR, key, k.SURFACES, None, manual, "BEF")
        rep["meta"] = {"date": "2026-10-01", "git_sha": "dd481c5", "source": "recorded run replayed with hand scores"}
        return rep
    return json.loads((RESULTS / entry["dir"] / "parcel_kit.json").read_text())


def collect() -> dict:
    key = k.load_key()
    runs = []
    for e in PROGRESSION:
        rep = load_run(e)
        row = {"id": e["id"], "label": e["label"], "date": rep["meta"].get("date"), "code": rep["meta"].get("git_sha"),
               "report": None if e.get("replay") else f"eval/results/{e['dir']}/parcel_kit.md", "surfaces": {}}
        for s in e["surfaces"]:
            body = rep["surfaces"].get(s)
            if not body:
                continue
            a = body["aggregate"]
            row["surfaces"][s] = {
                "parcels_scored": a["parcels"], "coverage": round(a["coverage"], 3), "accuracy": round(a["accuracy"], 3),
                "points": a["points"], "possible": a["possible"], "confident_wrong": a["cw"],
                "critical_misses": a["critical_misses"], "district_correct": a["a_correct"],
                "scoring": "hand scores on B/E/F" if e.get("replay") else "automatic",
            }
        runs.append((row, rep))
    current: dict[str, dict] = {}
    for row, rep in runs:
        for s, agg in row["surfaces"].items():
            if agg["parcels_scored"] == len(key["parcels"]):  # a surface counts as current only when all parcels were scored
                current[s] = {"run": row["id"], "date": row["date"], "code": row["code"], "report": row["report"], "aggregate": agg,
                              "fields": rep["surfaces"][s]["fields"]}
    return {
        "kit_version": key["version"], "parcels": [{"id": p["id"], "address": p["address"], "why": p["why"], "district": p["A"]["district"]} for p in key["parcels"]],
        "current": current, "progression": [r for r, _ in runs],
        "limits": LIMITS,
    }


LIMITS = [
    "Seven parcels show kinds of failure. They are not a statistically reliable accuracy rate.",
    "The answer key was built from primary sources but has not yet been reviewed by a Chicago architect or zoning attorney (the most interpretive parcels are P2, P3 and P6).",
    "Overlay truth comes from the same City service the product queries, so overlay scores are not independent evidence. District, bulk numbers and the task answers are.",
    "Use-question, parking and task answers are scored by expected-phrase rubrics that were written while looking at earlier runs, so agreement with a person's scores is in-sample.",
    "Chat answers vary from run to run; one run per row. Compare runs by the cases that fail, not by the third digit.",
    "Code text is current through the Council Journal of 2026-03-18; a later amendment is not in the key.",
]


def render(data: dict) -> str:
    key = k.load_key()
    cur = data["current"]
    L: list[str] = []
    L.append("# UrbanLayer parcel benchmark")
    L.append("")
    L.append("Seven hard Chicago parcels, each with an answer key built from primary sources, asked the same six questions of "
             "the product's **Property Profile** (a deterministic page) and of its **chat** (the same standard prompt, address "
             "only). It was built to find where a zoning tool is wrong, so it includes the failures.")
    L.append("")
    L.append("> **Read the limits before quoting a number** (section 6). Seven parcels; the key is not yet reviewed by a Chicago professional.")
    L.append("")
    L.append("## 1. Current results")
    L.append("")
    L.append("| Surface | Run | Parcels scored | Coverage | Accuracy | Confident-wrong fields | Wrong districts | Scoring |")
    L.append("|---|---|:-:|:-:|:-:|:-:|---|---|")
    for s in ("profile", "chat"):
        if s not in cur:
            continue
        c = cur[s]
        a = c["aggregate"]
        L.append(f"| {'Property Profile' if s == 'profile' else 'Chat'} | {c['date']} (`{c['code']}`) | {a['parcels_scored']}/7 | {_pct(a['coverage'])} | "
                 f"{_pct(a['accuracy'])} | {a['confident_wrong']} | {', '.join(a['critical_misses']) or 'none'} | {a['scoring']} |")
    L.append("")
    L.append("*Coverage* is the share of the 37 scored fields the tool made a claim on; *accuracy* is points earned (2 / 1 / 0) over "
             "points possible on the fields it answered; a *confident-wrong* field is wrong and stated without hedging; a *wrong "
             "district* is the critical failure, because everything else derives from it. The two surfaces' current runs come from "
             "different code versions (the most recent run that scored all seven parcels on each surface).")
    L.append("")
    L.append("## 2. Parcel by parcel")
    L.append("")
    L.append("Score per field: **2** correct, **1** partial, **0** wrong, **NP** no claim; **CW** marks a confident-wrong answer. "
             "Fields: A district, B use question, C bulk numbers, D overlays, E parking/transit (P3 and P5 only), F the parcel's task question.")
    L.append("")
    for p in key["parcels"]:
        pid = p["id"]
        L.append(f"### {pid} · {p['address']} · key district **{p['A']['district']}**")
        L.append("")
        L.append(f"*{p['why']}.*")
        L.append("")
        L.append("| Field | Question | Key answer | Profile | Chat |")
        L.append("|---|---|---|:-:|:-:|")
        for f in p["scored"]:
            spec = p[f]
            if f == "A":
                q, ans = "Zoning district", p["A"]["district"]
            elif f == "C":
                q = "Bulk numbers"
                ans = "; ".join(f"{n['name'].replace('_ft', '')} {', '.join(f'{v:g}' for v in n['accept'])}" for n in spec["numbers"])
            elif f == "D":
                q, ans = "Overlays", ", ".join(spec["expected"])
            else:
                q, ans = FIELD_NAMES[f], spec.get("answer", "")
            cells = []
            for s in ("profile", "chat"):
                fld = (cur.get(s, {}).get("fields", {}).get(pid, {}) or {}).get(f)
                cells.append(fld["label"] if fld else "")
            L.append(f"| {f} | {q} | {ans} | {cells[0]} | {cells[1]} |")
        L.append("")
    L.append("## 3. How the numbers moved")
    L.append("")
    L.append("Each row is a dated run of the real system on one code version (`make kit`), scored the same way. Every change here "
             "shipped because an earlier row showed a failure; the reports linked are the raw evidence.")
    L.append("")
    L.append("| Run | Date | Code | Profile accuracy / confident-wrong | Chat accuracy / confident-wrong | Chat wrong districts | Report |")
    L.append("|---|---|---|:-:|:-:|---|---|")
    for r in data["progression"]:
        prof, chat = r["surfaces"].get("profile"), r["surfaces"].get("chat")
        pc = f"{_pct(prof['accuracy'])} / {prof['confident_wrong']}" if prof else ""
        if chat:
            cc = f"{_pct(chat['accuracy'])} / {chat['confident_wrong']}"
            if chat["parcels_scored"] < 7:
                cc += f" ({chat['parcels_scored']} parcels)"
            wd = ", ".join(chat["critical_misses"]) or "none"
        else:
            cc, wd = "", ""
        rep = f"[report]({'../../' + r['report']})" if r["report"] else "recorded run in `eval/kit/baseline/`"
        L.append(f"| {r['label']} | {r['date']} | `{r['code']}` | {pc} | {cc} | {wd} | {rep} |")
    L.append("")
    L.append("## 4. What the first run found")
    L.append("")
    L.append("The starting point is the uncomfortable part, and it is kept on purpose. The Profile resolved the right district on "
             "all seven parcels but showed a false claim (that every transit-served parcel gets a density bonus; only dash-3 districts "
             "can, and only by entitlement) and never showed the number a unit count turns on (minimum lot area per unit). Chat, given "
             "only an address, located the parcel from a geocoded street point instead of the parcel, which put it in the neighboring "
             "district on two of seven parcels (a vacant RM-4.5 lot answered as RS-3, a landmark answered as a C1-3 parcel), invented "
             "bulk numbers from memory, and stopped at its token cap mid-answer on most parcels without saying so. A recent rezoning "
             "could not be stated at all, and a multi-parcel strip center's building area had been attributed to a single lot.")
    L.append("")
    L.append("## 5. The answer key")
    L.append("")
    L.append(f"Key version `{key['version']}`, in [`eval/kit/parcels.json`](../../eval/kit/parcels.json), with the source for every field. "
             "Sources: the City's open-data zoning layer and its zoning map service (overlays), the Municipal Code text "
             "(American Legal export, current through the Council Journal of 2026-03-18), ordinance PDFs, and Cook County Assessor "
             "data. Where the key and the product agree because they read the same City service, that is noted (overlays). The key "
             "fixed three errors in an earlier version that had used the product's own output as ground truth.")
    L.append("")
    L.append("## 6. Limits")
    L.append("")
    for s in data["limits"]:
        L.append(f"- {s}")
    L.append("")
    L.append("## 7. Reproduce it")
    L.append("")
    L.append("```bash")
    L.append("make kit-replay    # re-score the recorded runs: no network, no cost; reproduces the starting-point row")
    L.append("make kit           # run the live system on the 7 parcels, then score it (Profile is free; chat costs about $1)")
    L.append("PYTHONPATH=. python -m eval.benchmark   # regenerate this page from the committed results")
    L.append("```")
    L.append("")
    L.append("The scorer, rubrics and its tests are in [`eval/parcel_kit.py`](../../eval/parcel_kit.py). District, bulk numbers "
             "and overlays are scored mechanically; use, parking and task answers by expected-phrase rubrics; a person's scores can "
             "override any field (`--manual`), and every report states how often the automatic score agreed with the hand score.")
    L.append("")
    L.append("## 8. Scoring another tool")
    L.append("")
    L.append("UrbanLayer is the only tool published here for now; other tools will be added after review and a terms-of-service "
             "check. To score one yourself: enter each address **alone** (no PIN, no district), use the standard prompt below for "
             "chat tools, record the answer as shown without correcting it, and score against the key with the rubric above.")
    L.append("")
    L.append("Standard prompt (per parcel, with its use and task questions from the key):")
    L.append("")
    L.append("> " + key["prompt_template"].replace("{address}", "<ADDRESS>").replace("{use}", "<USE QUESTION>").replace("{task}", "<TASK QUESTION>"))
    L.append("")
    L.append("| Parcel | A district | B use | C bulk | D overlays | E parking/transit | F task | Notes |")
    L.append("|---|:-:|:-:|:-:|:-:|:-:|:-:|---|")
    for p in key["parcels"]:
        L.append(f"| {p['id']} {p['address']} | | | | | {'' if 'E' in p['scored'] else 'n/a'} | | |")
    L.append("")
    L.append("*One generic-LLM reference run (a model with web search and no access to this repository) was recorded once on "
             "2026-10-01 for context: it made a claim on about a third of the fields and was right on about half of those. It is "
             "one model and one harness, and its raw output is not part of this repository, so it is not reproducible from here.*")
    L.append("")
    return "\n".join(L)


def build() -> tuple[str, str]:
    data = collect()
    return render(data), json.dumps(data, indent=1, ensure_ascii=False) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="exit 1 if the committed page differs from what the results generate")
    args = ap.parse_args(argv)
    md, js = build()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    if args.check:
        stale = [p.name for p, new in ((OUT_DIR / "README.md", md), (OUT_DIR / "results.json", js)) if not p.exists() or p.read_text() != new]
        if stale:
            print(f"stale: {', '.join(stale)}; run `make benchmark`", file=sys.stderr)
            return 1
        print("benchmark page is current")
        return 0
    (OUT_DIR / "README.md").write_text(md)
    (OUT_DIR / "results.json").write_text(js)
    print(f"wrote {OUT_DIR / 'README.md'} and results.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
