"""Build the answer-key review packet: docs/benchmark/review-packet.md.

The packet is BLIND: it holds the key, its sources and the questions that need judgment,
and none of the tool's own answers, so the reviewer cannot be anchored on them. It is
generated from eval/kit/parcels.json, so it cannot drift from the key being reviewed.

    PYTHONPATH=. python -m eval.review_packet           # rewrite the packet
    PYTHONPATH=. python -m eval.review_packet --check   # fail if it is stale
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from eval import parcel_kit as k

OUT = Path(__file__).resolve().parent.parent / "docs" / "benchmark" / "review-packet.md"

# Fields that turn on a reading of the code rather than a lookup, each with the specific
# question to put to the reviewer. Everything else is a mechanical lookup the reviewer may skim.
JUDGMENT: dict[str, str] = {
    "P2.B": "Is multi-unit residential permitted by right in RM-4.5 on this lot, as the use table reads?",
    "P2.D": "A 606 district is mapped here. Does it leave RM-4.5 density unchanged (17-7-0591), in contrast to P6 where it lowers the minimum lot area?",
    "P2.F": "Is 4 the right by-right maximum? Does the code round a fractional unit count down, and is any relief available by right that would reach 6?",
    "P3.B": "Is ground-floor dwelling a special use, with units above the ground floor permitted, in B1-2?",
    "P3.E": "Does transit proximity reduce required parking only, with no density or FAR bonus, at a dash-2 district?",
    "P3.F": "Same question as E, plus: are the height and FAR figures the ones that govern a mixed-use building?",
    "P4.C": "Are these the right PD 835 figures: FAR 26.0 from the bulk table, and a height of 1,125 ft as modified by a 2010 minor-change letter?",
    "P5.E": "Is parking reducible by up to 100% for a transit-served location, with no added parking for reusing a contributing building in a landmark district?",
    "P5.F": "Does an individually landmarked building in a landmark district require the Commission on Chicago Landmarks' written approval before demolition or a new building?",
    "P6.B": "Is a two-flat permitted in RS-3, and does the 606 district lower the minimum lot area per unit from 2,500 to 1,500?",
    "P6.C": "Which minimum lot area per unit applies here: 1,500 (606 district) or 2,500?",
    "P6.F": "Is a coach house allowed here with exactly the annual limit and owner-occupancy conditions of ADU Zone 10?",
    "P7.A": "The rezoning ordinance passed 2026-06-17. Was it in effect on 2026-10-01 (publication and effective date), so that RT-4 rather than M1-2 is the district in effect?",
}

FIELD_LABEL = {"A": "Zoning district", "B": "Use question", "C": "Bulk and density numbers", "D": "Overlays and designations",
               "E": "Parking / transit rule", "F": "Task question"}


def _numbers(spec: dict) -> list[tuple[str, str, str]]:
    names = {"far": "Floor area ratio", "height_ft": "Height (ft)", "mla": "Minimum lot area per dwelling unit (sq ft)"}
    return [(names.get(n["name"], n["name"]), " or ".join(f"{v:g}" for v in n["accept"]), n["basis"]) for n in spec["numbers"]]


def render() -> str:
    key = k.load_key()
    L: list[str] = []
    L += [
        "# Answer-key review packet",
        "",
        "We are publishing a benchmark of how accurately zoning tools answer questions about hard Chicago parcels. "
        "Its value rests on the answer key being right. This packet is that key, with the source for each answer. "
        "We are asking you to check our reading of the sources, not to answer from memory.",
        "",
        "**This packet is blind.** It contains no tool's answers, ours or anyone's, so your review is not anchored on them.",
        "",
        "## What we are asking",
        "",
        "1. For each field marked **Judgment**, open the cited source and tell us **agree**, **disagree** or **unsure**, "
        "with a sentence on why. If you disagree, tell us what the right answer is and where it comes from.",
        "2. Skim the other fields. They are lookups (a district from the City's zoning layer, a number from a code table). "
        "Flag anything that looks wrong.",
        "3. Tell us what is missing: situations in which a tool would likely get Chicago zoning wrong that these seven parcels do not test. "
        "We are growing the set to about 25 parcels and will pick from your answer.",
        "",
        f"Expected effort: about {len([j for j in JUDGMENT])} judgment fields, roughly an hour with the code open.",
        "",
        "## As of",
        "",
        f"- Key version `{key['version']}`, built 2026-10-01.",
        "- Municipal Code text current through the Council Journal of 2026-03-18 (American Legal export of Title 17). "
        "An amendment after that date is not reflected; tell us if one changes an answer.",
        "- Parcel facts come from the City of Chicago zoning layer (Data Portal `dj47-wfun`) and Zoning MapServer, Cook County Assessor data, and ordinance PDFs.",
        "- Overlay answers (field D) read the same City map service that tools use, so they check that a tool reports the map correctly, not that the map is right. "
        "They are not the focus of this review.",
        "",
        "## The parcels",
        "",
    ]
    for p in key["parcels"]:
        pid = p["id"]
        pin = p.get("pin") or "building PIN not in the Parcel Universe (condominium building)"
        L += [f"### {pid} · {p['address']}", "", f"PIN: {pin}. Why it is in the set: {p['why']}.", ""]
        L += [f"Question put to a tool, field B: *{p['use_question']}*  ", f"Field F: *{p['task_question']}*", ""]
        L += ["| Field | Our answer | Source | Review |", "|---|---|---|---|"]
        for f in p["scored"]:
            spec = p[f]
            tag = f"{pid}.{f}"
            if f == "A":
                ans = spec["district"] + (f" (not {', '.join(spec['wrong'])}, which a geocoder lands in)" if spec["wrong"] else "")
                src = spec["basis"]
                rows = [(FIELD_LABEL[f], ans, src)]
            elif f == "C":
                rows = [(f"C · {n}", v, b) for n, v, b in _numbers(spec)]
            elif f == "D":
                rows = [(FIELD_LABEL[f], ", ".join(spec["expected"]), spec["basis"])]
            else:
                ans = spec["answer"]
                rows = [(FIELD_LABEL[f], ans, "see the code sections cited in the answer")]
            for label, ans, src in rows:
                mark = "**Judgment**" if tag in JUDGMENT else "skim"
                L.append(f"| {label} | {ans} | {src} | {mark} |")
        L.append("")
        qs = [(f"{pid}.{f}", JUDGMENT[f"{pid}.{f}"]) for f in p["scored"] if f"{pid}.{f}" in JUDGMENT]
        if qs:
            L.append("Questions:")
            L.append("")
            L += [f"- **{tag}**: {q}" for tag, q in qs]
            L.append("")
    L += [
        "## How to reply",
        "",
        "Reply in any form, as long as each judgment field is named by its tag (for example `P2.F`). A table like this is easiest:",
        "",
        "| Tag | agree / disagree / unsure | Note (and the right answer, with its source, if you disagree) |",
        "|---|---|---|",
        "| P2.F | | |",
        "",
        "Also tell us how you would like to be credited, if at all. We will publish your role and credentials. "
        "We will publish your name only if you say yes. Every disagreement will be published alongside the agreement rate, whether or not we change the key.",
        "",
    ]
    return "\n".join(L)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)
    text = render()
    if args.check:
        if not OUT.exists() or OUT.read_text() != text:
            print("stale review packet; run `python -m eval.review_packet`", file=sys.stderr)
            return 1
        print("review packet is current")
        return 0
    OUT.write_text(text)
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
