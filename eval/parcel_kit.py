"""Parcel kit: score UrbanLayer on a fixed 7-parcel Chicago answer key.

Each parcel in ``eval/kit/parcels.json`` has an answer key built from primary
sources (City zoning layer, Municipal Code text, ordinance PDFs, Assessor data).
Two surfaces are scored on the same six fields:

  profile  the deterministic Property Profile (``GET /api/scorecard``), plus the
           verdict text the page computes from it
  chat     the standard research prompt typed into ``POST /chat`` with the
           address only (no PIN), i.e. what a cold user gets

Fields (``eval/kit/parcels.json`` -> ``fields``):
  A district (critical)   B use question   C bulk numbers   D overlays
  E parking/transit (P3, P5 only)          F task question

Each field scores 2 / 1 / 0 / NP (no claim), with CW flagged separately for a
confident-wrong claim. A, C and D are scored mechanically (district token,
numbers near FAR/height/lot-area-per-unit, the overlay set). B, E and F use
expected-phrase rubrics from the key, and any field can be overridden by a
hand-scores file (``--manual``) so a person's judgment can replace the rubric.
The report always shows how often the automatic score agrees with the hand
score, so a weak rubric is visible rather than silently trusted.

Usage:
  # score recorded runs (no network): reproduces the 2026-10-01 baseline
  PYTHONPATH=. python -m eval.parcel_kit --replay eval/kit/baseline/2026-10-01

  # run the real system (needs a backend on :8001; chat costs ~$0.1 per parcel)
  PYTHONPATH=. python -m eval.parcel_kit --full http://localhost:8001 --out-dir eval/results/$(date +%F)
  PYTHONPATH=. python -m eval.parcel_kit --full http://localhost:8001 --parcels P2,P5 --surfaces chat

Chat is rate-limited for anonymous callers; for a full run start the backend
with RATE_LIMIT_ANON_DAY=50 RATE_LIMIT_ANON_HOUR=50.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import math
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

KIT_DIR = Path(__file__).resolve().parent / "kit"
KEY_FILE = KIT_DIR / "parcels.json"
VERDICT_SCRIPT = KIT_DIR / "verdict_text.mjs"
HISTORY_CSV = Path(__file__).resolve().parent / "results" / "history.csv"

FIELDS = ["A", "B", "C", "D", "E", "F"]
SURFACES = ["profile", "chat"]
# Item number each field occupies in the standard prompt; chat answers are
# scored on the matching numbered section when the model kept that structure.
FIELD_SECTION = {"A": 1, "B": 2, "C": 3, "D": 4, "E": 5, "F": 6}


# --------------------------------------------------------------------------
# Results
# --------------------------------------------------------------------------

@dataclass
class FieldResult:
    score: int | None  # 2 / 1 / 0, None = NP (no claim)
    cw: bool = False
    basis: str = "auto"  # auto | manual
    auto_score: int | None = None
    auto_cw: bool = False
    detail: str = ""

    def label(self) -> str:
        s = "NP" if self.score is None else str(self.score)
        return s + (" CW" if self.cw else "")


def parse_hand_score(raw: str) -> tuple[int | None, bool]:
    """'2' -> (2, False), '1CW' -> (1, True), 'NP' -> (None, False)."""
    raw = raw.strip().upper().replace(" ", "")
    cw = raw.endswith("CW")
    raw = raw.removesuffix("CW")
    return (None if raw == "NP" else int(raw)), cw


def load_key(path: Path = KEY_FILE) -> dict:
    return json.loads(path.read_text())


def build_prompt(key: dict, parcel: dict) -> str:
    return key["prompt_template"].format(
        address=parcel["address"], use=parcel["use_question"], task=parcel["task_question"],
    )


# --------------------------------------------------------------------------
# Text helpers (chat answers)
# --------------------------------------------------------------------------

_SECTION_RE = re.compile(r"^(?:#{2,4}\s*(?:[^\w\s]+\s*)?|\*\*)(\d)\s*[.)]", re.M)


def split_sections(text: str) -> dict[int, str]:
    """Numbered answer items -> their text. Only sequential headings count
    ('## 3. Bulk' or '**3. Bulk**'), so a stray numbered list can't split it."""
    marks: list[tuple[int, int]] = []
    last = 0
    for m in _SECTION_RE.finditer(text):
        n = int(m.group(1))
        if n == last + 1 or (n > last and 1 <= n <= 6 and not marks):
            marks.append((n, m.start()))
            last = n
    out: dict[int, str] = {}
    for i, (n, start) in enumerate(marks):
        end = marks[i + 1][1] if i + 1 < len(marks) else len(text)
        out[n] = text[start:end]
    return out


def field_text(sections: dict[int, str], text: str, fld: str) -> str:
    """Chat text a field should be scored on: its numbered item when the model
    kept the structure, else the whole answer (a missing item is then NP)."""
    if len(sections) >= 3:
        return sections.get(FIELD_SECTION[fld], "")
    return text


_DISTRICT_RE = re.compile(
    r"\b(R[STM]-?\d(?:\.\d)?|[BC][1-3]-\d|M[1-3]-\d|D[CXRS]-\d+|PMD[- ]?\d+"
    r"|PD\s?(?:No\.?\s?)?\d+|Planned Development\s?(?:No\.?\s?)?\d+)\b",
    re.I,
)


def norm_district(s: str) -> str:
    s = s.upper()
    m = re.search(r"PLANNED DEVELOPMENT\s*(?:NO\.?\s*)?#?(\d+)", s) or re.search(r"\bPD\s*(?:NO\.?\s*)?#?(\d+)", s)
    if m:
        return "PD" + m.group(1)
    return re.sub(r"[\s-]+", "", s)


def first_district(text: str) -> str | None:
    m = _DISTRICT_RE.search(text)
    return norm_district(m.group(1)) if m else None


# --------------------------------------------------------------------------
# Overlays
# --------------------------------------------------------------------------

# overlay id -> /api/scorecard regulatory flag(s)
PROFILE_OVERLAY_FLAGS = {
    "pd": ["in_planned_development"],
    "landmark_building": ["is_landmark_building"],
    "historic_district": ["in_historic_district", "in_landmark_district"],
    "national_register": ["on_national_register"],
    "tod": ["in_tod_area"],
    "aro": ["in_aro_zone"],
    "ssa": ["in_ssa"],
    "special_district": ["in_special_district"],
    "adu": ["in_adu_area"],
    "pedestrian_street": ["on_pedestrian_street"],
    "lakefront": ["in_lakefront_protection"],
    "pmd": ["in_pmd"],
}

CHAT_OVERLAY_PATTERNS = {
    "pd": r"(?<!amendment, )(?<!amendment or )planned development|\bPD[ -]?\d+",  # not "map amendment, planned development, or ARO"
    "landmark_building": r"individual (?:chicago )?landmark|landmark building|designated (?:chicago )?landmark",
    "historic_district": r"landmark district|historic district|\bHD-\d+",
    "national_register": r"national register",
    "tod": r"transit[- ]oriented|\bTOD\b",
    "aro": r"affordable requirements|\bARO\b",
    "ssa": r"special service area|\bSSA\b",
    "special_district": r"predominance of the block|\b606\b|special district",
    "adu": r"\bADU\b|additional dwelling|coach house",
    "pedestrian_street": r"pedestrian[- ]street(?! design)",
    "lakefront": r"lakefront protection",
    "pmd": r"planned manufacturing|\bPMD\b",
}
# An ADU hit on a non-RS parcel is true in outcome (ADUs are by right there), so
# it is never counted as a false overlay; it only counts when the key expects it.
NEVER_FALSE = {"adu"}

_NEG_BEFORE = re.compile(r"\b(no|not|none|neither|nor|without|isn't|doesn't|does not|is not|aren't|absent|exceed|exceeds|outside|beyond)\b", re.I)
_SENT_BREAK = re.compile(r"(?<=[.!?])\s+|:\*\*\s*")
_NEG_SAME_SENTENCE = re.compile(
    r"\b(?:does|do|is)\s+\*{0,2}not\b"
    r"|\b(?:doesn't|isn't)\b"
    r"|\bnot\b\*{0,2}\s+(?:apply|applicable|qualify|eligible|within|in an? |located|meet|present|designated)",
    re.I,
)
_NEG_AFTER = re.compile(
    r"^(?:\s*\(\w{2,6}\)|\s*/\s*[\w-]+(?:\s[\w-]+){0,2}|\s+(?:overlay|district|area|zone|designation))*[\s*|:—–)(-]*(?:[❌✗✘🚫]\s*)?\**\s*(?:not\b|no\b|none\b|n/a)"  # "| X | ❌ No |", "X: not ..."
    r"|^[^\n.]{0,60}?\b(?:does not|doesn't|do not|is not|isn't|not) (?:apply|applicable|qualify|eligible|within|in)\b",
    re.I,
)


_CELL_NO = re.compile(r"^[\s*]*(?:[❌✗✘🚫]\s*)?\**\s*(?:not\b|no\b|none\b|n/a)", re.I)


def _table_row_denies(line: str, pos: int) -> bool:
    """In '| **Overlay** | ❌ No | ... |' the cell after the one holding the
    mention carries the answer."""
    cells, offset, idx = line.split("|"), 0, 0
    for i, c in enumerate(cells):
        if offset <= pos <= offset + len(c):
            idx = i
            break
        offset += len(c) + 1
    nxt = cells[idx + 1] if idx + 1 < len(cells) else ""
    return bool(_CELL_NO.match(nxt)) or bool(_NEG_BEFORE.search(cells[idx][: max(0, pos - offset)]))


def chat_overlays(text: str) -> tuple[set[str], set[str]]:
    """(asserted, denied) overlay ids mentioned in a chat answer. A mention is a
    denial when 'no/not/none' sits right before or after it on the same line;
    an overlay asserted anywhere is not also counted as denied."""
    asserted: set[str] = set()
    denied: set[str] = set()
    for oid, pat in CHAT_OVERLAY_PATTERNS.items():
        for m in re.finditer(pat, text, re.I):
            line_start = text.rfind("\n", 0, m.start()) + 1
            line_end = text.find("\n", m.end())
            line = text[line_start : line_end if line_end != -1 else len(text)]
            if line.lstrip().startswith("|"):
                if _table_row_denies(line, m.start() - line_start):
                    denied.add(oid)
                else:
                    asserted.add(oid)
                continue
            # a mention inside an open parenthetical list is a process example
            # ("(map amendment, special use, or planned development)"), not a claim
            head = text[line_start : m.start()]
            if head.count("(") > head.count(")"):
                continue
            # negation anywhere earlier in the same sentence ("No Planned Development,
            # Landmark, or PMD overlays apply") covers every item in a list
            sent_start = max([line_start] + [line_start + b.end() for b in _SENT_BREAK.finditer(text[line_start : m.start()])])
            before = text[max(sent_start, m.start() - 160) : m.start()]
            after = text[m.end() : m.end() + 120].split("\n", 1)[0]
            if _NEG_BEFORE.search(before) or _NEG_AFTER.match(after) or _NEG_SAME_SENTENCE.search(after.split(". ")[0]):
                denied.add(oid)
            else:
                asserted.add(oid)
    return asserted, denied - asserted


def profile_overlays(resp: dict) -> set[str]:
    reg = (resp.get("context") or {}).get("regulatory") or {}
    return {oid for oid, flags in PROFILE_OVERLAY_FLAGS.items() if any(reg.get(f) for f in flags)}


def score_overlays(expected: list[str], asserted: set[str], denied: set[str]) -> tuple[int, bool, str]:
    exp = set(expected)
    found = exp & asserted
    false = asserted - exp - NEVER_FALSE
    wrongly_denied = denied & exp
    if found == exp and not false:
        score = 2
    elif len(found) / len(exp) >= 0.5:
        score = 1
    else:
        score = 0
    bits = [f"found {len(found)}/{len(exp)}"]
    if exp - found:
        bits.append("missing " + ",".join(sorted(exp - found)))
    if false:
        bits.append("false " + ",".join(sorted(false)))
    if wrongly_denied:
        bits.append("denied " + ",".join(sorted(wrongly_denied)))
    return score, bool(false or wrongly_denied), "; ".join(bits)


# --------------------------------------------------------------------------
# Numbers (field C)
# --------------------------------------------------------------------------

_DEC = r"(?<![\d.§/-])(\d{1,2}\.\d{1,2})(?![\d%-])"


# Lines that quote a number about something other than this parcel's district
# standard: accessory structures, comparisons, the building as built.
_OFF_TOPIC_LINE = re.compile(
    r"coach house|accessory|rooftop|garage|\bADU\b|fence|parking|setback|for reference|reference\)|implied|actual|existing|as built",
    re.I,
)
# a lot-area number that describes THIS parcel's size, not the district standard
_PARCEL_SIZE = re.compile(r"(?:land|lot|site|parcel)(?:'s)?\s*(?:area|size)?\s*(?:is|of|:|=)?[^.\n]{0,15}$|parcel is[^.\n]{0,15}$", re.I)
# a number the model offers while saying it can't confirm it
_HEDGE = re.compile(
    r"cannot|can't|could not|couldn't|not able|unable|typically|usually|generally|likely|approximately|probably|"
    r"\bmay\b|might|uncertain|unverified|not confirmed",
    re.I,
)


def _collect(text: str, keyword: str, width: int, value_re: str, to_float, flags: int = 0) -> list[tuple[float, bool]]:
    """(value, hedged) for numbers stated within ``width`` chars after a keyword,
    cut at the paragraph end; lines about off-topic structures are skipped."""
    out: list[tuple[float, bool]] = []
    seen: set[int] = set()  # keywords repeat on a line; count each number once
    for km in re.finditer(keyword, text, re.I):
        ls = text.rfind("\n", 0, km.start()) + 1
        le = text.find("\n", km.end())
        if _OFF_TOPIC_LINE.search(text[ls : le if le != -1 else len(text)]):
            continue
        base = km.end()
        window = text[base : base + width].split("\n\n", 1)[0]
        for vm in re.finditer(value_re, window, flags):
            pos = base + vm.start()
            if _PARCEL_SIZE.search(text[max(0, pos - 40) : pos].replace("*", "")) and "lot area" in keyword:
                continue
            vs = text.rfind("\n", 0, pos) + 1
            ve = text.find("\n", pos)
            line = text[vs : ve if ve != -1 else len(text)]
            if pos in seen or _OFF_TOPIC_LINE.search(line):
                continue
            seen.add(pos)
            out.append((to_float(vm.group(1)), bool(_HEDGE.search(line))))
    return out


def chat_numbers(text: str) -> dict[str, list[float]]:
    """Numbers a chat answer states near FAR / height / lot-area-per-unit. The
    ``<name>_hedged`` lists hold the subset the model offered with a hedge."""
    found = {
        "far": _collect(text, r"\bFAR\b|floor[- ]area ratio", 120, _DEC, float),
        "height_ft": _collect(
            text, r"height", 120, r"(?<![\d.§-])(\d[\d,]*)\s*(?:ft\b|feet\b|foot\b)", lambda x: float(x.replace(",", ""))
        ),
        "mla": _collect(
            text, r"lot area per (?:dwelling )?unit|\bMLA\b|per dwelling unit|\bLAPDU\b", 220,
            r"(?<![\d.§-])(\d{1,2},\d{3}|\d{3,4})(?![\d-])\s*(?:sq|sf|square)", lambda x: float(x.replace(",", "")), re.I,
        ),
    }
    out: dict[str, list[float]] = {}
    for name, vals in found.items():
        out[name] = [v for v, _ in vals]
        out[name + "_hedged"] = [v for v, h in vals if h]
    return out


def profile_numbers(resp: dict, spec_numbers: list[dict]) -> dict[str, list[float]]:
    zd = resp.get("zone_definition") or {}
    out: dict[str, list[float]] = {"far": [], "height_ft": [], "mla": []}
    if isinstance(zd.get("far"), (int, float)):
        out["far"] = [float(zd["far"])]
    h = zd.get("max_height")
    if isinstance(h, str):
        # "45–47 ft (varies by lot frontage)" -> the numbers before the first "ft"
        out["height_ft"] = [float(x) for x in re.findall(r"\d+", h.split("ft")[0])] if "ft" in h else []
    for n in spec_numbers:
        if n["name"] == "mla":
            for f in n.get("profile_fields", ["min_lot_area_per_unit"]):
                v = zd.get(f)
                if isinstance(v, (int, float)):
                    out["mla"] = [float(v)]
                    break
    return out


def score_numbers(spec_numbers: list[dict], stated: dict[str, list[float]]) -> tuple[int | None, bool, str]:
    matched = wrong = answered = 0
    hedged_all = True
    bits = []
    for n in spec_numbers:
        vals = stated.get(n["name"], [])
        if not vals:
            bits.append(f"{n['name']} absent")
            continue
        answered += 1
        ok = any(abs(v - a) <= n["tol"] for v in vals for a in n["accept"])
        if ok:
            matched += 1
            bits.append(f"{n['name']} ok")
        else:
            wrong += 1
            hedged = all(v in stated.get(n["name"] + "_hedged", []) for v in vals)
            hedged_all = hedged_all and hedged
            bits.append(
                f"{n['name']} wrong{' (hedged)' if hedged else ''} "
                f"({','.join(f'{v:g}' for v in vals)} vs {','.join(f'{a:g}' for a in n['accept'])})"
            )
    if wrong:
        return 0, not hedged_all, "; ".join(bits)
    if not answered:
        return None, False, "; ".join(bits)
    return (2 if matched == len(spec_numbers) else 1), False, "; ".join(bits)


# --------------------------------------------------------------------------
# Phrase rubrics (fields B, E, F)
# --------------------------------------------------------------------------

def score_phrases(rubric: dict | None, text: str) -> tuple[int | None, bool, str]:
    """groups: every group needs one regex hit for a 2, some hits give a 1.
    partial: groups that earn a 1 when the full groups don't match.
    wrong: any hit means a 0 and CW. forbid: any hit flags CW and caps at 1
    (right conclusion carrying a false claim). none: score when nothing hit."""
    if not rubric:
        return None, False, "no rubric"

    def hit(group: list[str]) -> bool:
        return any(re.search(p, text, re.I) for p in group)

    if any(re.search(p, text, re.I) for p in rubric.get("wrong", [])):
        return 0, True, "matched a wrong-claim pattern"
    hits = [hit(g) for g in rubric["groups"]]
    if all(hits):
        score: int | None = 2
    elif any(hits):
        score = 1
    elif rubric.get("partial") and all(hit(g) for g in rubric["partial"]):
        score = 1
    else:
        score = None if rubric.get("none", "NP") == "NP" else int(rubric["none"])
    cw = False
    if any(re.search(p, text, re.I) for p in rubric.get("forbid", [])):
        cw = True
        score = 1 if score is None or score >= 1 else score
    return score, cw, f"groups {sum(hits)}/{len(hits)}"


# --------------------------------------------------------------------------
# Per-surface views
# --------------------------------------------------------------------------

def profile_text(resp: dict, verdict: dict | None) -> str:
    zd = resp.get("zone_definition") or {}
    reg = (resp.get("context") or {}).get("regulatory") or {}
    uy = (resp.get("context") or {}).get("unit_yield") or {}
    parts = [zd.get("uses") or "", zd.get("notes") or "", zd.get("lot_area_note") or "", uy.get("arithmetic") or ""]
    parts += [f"{o.get('name', '')} {o.get('description', '')} {o.get('detail') or ''}" for o in reg.get("overlays") or []]
    adu = (resp.get("context") or {}).get("adu") or {}
    parts.append(adu.get("note") or "")
    if verdict:
        parts += [verdict.get("headline", ""), *verdict.get("reasons", []), *verdict.get("caveats", []), verdict.get("next_step", "")]
    return "\n".join(p for p in parts if p)


def score_parcel_surface(parcel: dict, surface: str, data: dict | None, verdict: dict | None = None) -> dict[str, FieldResult]:
    """Automatic scores for one parcel on one surface. ``data`` is the raw
    /api/scorecard response (profile) or the saved chat run (chat)."""
    out: dict[str, FieldResult] = {}
    if data is None:
        return out
    if surface == "profile":
        text = profile_text(data, verdict)
        sections: dict[int, str] = {}
    else:
        text = data.get("text") or ""
        sections = split_sections(text)

    def ftext(fld: str) -> str:
        return text if surface == "profile" else field_text(sections, text, fld)

    for fld in parcel["scored"]:
        spec = parcel[fld]
        if fld == "A":
            want = norm_district(spec["district"])
            if surface == "profile":
                got = norm_district(((data.get("context") or {}).get("parcel_zoning") or {}).get("zone_class") or "") or None
            else:
                got = first_district(ftext("A")[:700])
            if got is None:
                res = FieldResult(None, detail="no district stated")
            elif got == want:
                res = FieldResult(2, detail=f"district {got}")
            else:
                res = FieldResult(0, True, detail=f"district {got}, key {want}")
        elif fld == "C":
            stated = profile_numbers(data, spec["numbers"]) if surface == "profile" else chat_numbers(ftext("C"))
            score, cw, detail = score_numbers(spec["numbers"], stated)
            res = FieldResult(score, cw, detail=detail)
        elif fld == "D":
            if surface == "profile":
                asserted, denied = profile_overlays(data), set()
            else:
                asserted, denied = chat_overlays(ftext("D"))
            score, cw, detail = score_overlays(spec["expected"], asserted, denied)
            res = FieldResult(score, cw, detail=detail)
        else:
            score, cw, detail = score_phrases(spec.get(surface), ftext(fld))
            res = FieldResult(score, cw, detail=detail)
        res.auto_score, res.auto_cw = res.score, res.cw
        out[fld] = res
    return out


def apply_manual(results: dict[str, FieldResult], hand: dict[str, str] | None, fields: str, forced: set[str] | None = None) -> None:
    """Hand scores replace the automatic score for ``fields`` and for any cell
    named in ``forced`` (a documented exception, listed in the report)."""
    for fld, raw in (hand or {}).items():
        if fld in results and (fld in fields or fld in (forced or set())):
            score, cw = parse_hand_score(raw)
            res = results[fld]
            res.score, res.cw, res.basis = score, cw, "manual"


# --------------------------------------------------------------------------
# Resolution + truncation (chat vs profile)
# --------------------------------------------------------------------------

def _feet(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 20_902_231  # earth radius in feet
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


_PIN_RE = re.compile(r"(?<!\d)(\d{14})(?!\d)|(?<!\d)(\d{2}-\d{2}-\d{3}-\d{3}-\d{4})(?!\d)")


def resolution_check(profile: dict | None, chat: dict | None) -> dict[str, Any]:
    """How the chat located the parcel versus the Profile's authoritative PIN."""
    out: dict[str, Any] = {}
    if profile:
        out["profile_pin"] = profile.get("resolved_pin")
        out["profile_confidence"] = profile.get("resolved_confidence")
    if chat:
        loc = chat.get("plan_location") or {}
        out["chat_resolved_address"] = loc.get("resolved_address")
        m = _PIN_RE.search(chat.get("text") or "")
        pin = (m.group(1) or m.group(2).replace("-", "")) if m else None
        out["chat_pin_in_text"] = pin
        if profile and pin and profile.get("resolved_pin"):
            out["chat_pin_matches"] = pin == profile["resolved_pin"]
        if profile and loc.get("resolved_lat") is not None and profile.get("resolved_lat") is not None:
            out["point_gap_ft"] = round(_feet(loc["resolved_lat"], loc["resolved_lon"], profile["resolved_lat"], profile["resolved_lon"]))
        pa, ca = profile and profile.get("community_area_name"), loc.get("resolved_community_area_name")
        if pa and ca:
            out["community_area_matches"] = pa.lower() == ca.lower()
    return out


# Context fields the prompt tells the model never to name to the user.
_INTERNAL_FIELD_NAMES = ("zone_definition", "unit_yield", "tod_benefits", "density_bonus_eligible", "parcel_resolution", "parcel_pin", "returned null")
# overlay ids the key uses -> the provenance keys a Profile may file them under
_OVERLAY_PROVENANCE_KEYS = {
    "pd": ["planned_development"], "landmark_building": ["landmark_building"],
    "historic_district": ["historic_district", "landmark_district"], "national_register": ["national_register"],
    "tod": ["tod_cta", "tod_metra"], "aro": ["aro_zone"], "ssa": ["ssa"],
    "special_district": ["special_district"], "adu": ["adu_area"],
    "pedestrian_street": ["pedestrian_street"], "lakefront": ["lakefront_protection"], "pmd": ["pmd_subarea"],
}
_NUMBER_PROVENANCE_KEYS = {"far": "zoning.far", "height_ft": "zoning.max_height", "mla": "zoning.min_lot_area_per_unit"}


def provenance_check(parcel: dict, profile: dict | None) -> dict[str, Any] | None:
    """Does every district, standard and expected overlay the Profile states carry a
    dated source? None when the payload has no provenance at all (an older run)."""
    if not profile or "provenance" not in profile:
        return None
    prov = profile.get("provenance") or {}

    def dated(key: str) -> bool:
        e = prov.get(key) or {}
        return any(isinstance(e.get(f), str) and re.match(r"^\d{4}-\d{2}-\d{2}$", e[f]) for f in ("as_of", "effective_date", "query_date"))

    required: list[str] = ["zoning.district"]  # field A: always answered by the Profile
    nums = profile_numbers(profile, parcel["C"]["numbers"])
    for n in parcel["C"]["numbers"]:
        key = _NUMBER_PROVENANCE_KEYS.get(n["name"])
        if key and nums.get(n["name"]):
            required.append(key)
    present = profile_overlays(profile)
    layer_types = {o.get("layer_type") for o in ((profile.get("context") or {}).get("regulatory") or {}).get("overlays") or []}
    for oid in parcel["D"]["expected"]:
        if oid in present:
            keys = [f"overlay.{lt}" for lt in _OVERLAY_PROVENANCE_KEYS.get(oid, [oid]) if lt in layer_types]
            required.append(keys[0] if keys else f"overlay.{oid}")
    missing = [k for k in required if not dated(k)]

    def source_dated(key: str) -> bool:  # the source itself says how current it is (not just our query date)
        e = prov.get(key) or {}
        return any(isinstance(e.get(f), str) and re.match(r"^\d{4}-\d{2}-\d{2}$", e[f]) for f in ("as_of", "effective_date"))

    return {
        "required": len(required), "dated": len(required) - len(missing), "missing": missing,
        "source_dated": sum(1 for k in required if source_dated(k)),
    }


_CUT_OFF_NOTICE = re.compile(r"answer was cut off before it finished|respuesta se cortó antes de terminar", re.I)


def truncation_check(chat: dict | None) -> dict[str, Any]:
    """Did the answer reach item 6, does it end on a finished sentence, and when
    it was cut off, did the product say so (notice text and/or API flag)?"""
    if not chat:
        return {}
    text = (chat.get("text") or "").rstrip()
    notice = bool(_CUT_OFF_NOTICE.search(text))
    body = _CUT_OFF_NOTICE.split(text, 1)[0] if notice else text
    body = body.rstrip(" \n-*_")  # the notice is set off by a rule and italics
    sections = split_sections(body)
    leaks = sorted({n for n in _INTERNAL_FIELD_NAMES if n in text})
    errored = bool(chat.get("error"))
    out = {
        "errored": errored,
        "field_name_leaks": leaks,
        "chars": len(text),
        "item6_present": 6 in sections,
        "ends_cleanly": bool(body) and body[-1] in '.!?)`*"' and not notice,
        "notice_shown": notice,
    }
    if "truncated" in chat:  # set by the SSE done event (F4)
        out["truncated_flag"] = chat["truncated"]
    # A silent cut-off is the defect: the answer stops short and nothing says so.
    out["silently_cut_off"] = not errored and not out["ends_cleanly"] and not notice and not chat.get("truncated")
    return out


# --------------------------------------------------------------------------
# Aggregation
# --------------------------------------------------------------------------

def aggregate(per_parcel: dict[str, dict[str, FieldResult]], n_scored: int) -> dict[str, Any]:
    earned = answered = cw = 0
    cw_fields: list[str] = []
    critical: list[str] = []
    a_correct = 0
    for pid, fields in per_parcel.items():
        for fld, r in fields.items():
            if r.score is not None:
                answered += 1
                earned += r.score
            if r.cw:
                cw += 1
                cw_fields.append(f"{pid}.{fld}")
        a = fields.get("A")
        if a is not None:
            if a.score == 0:
                critical.append(pid)
            if a.score == 2:
                a_correct += 1
    return {
        "scored_fields": n_scored,
        "answered": answered,
        "coverage": answered / n_scored if n_scored else 0.0,
        "points": earned,
        "possible": 2 * answered,
        "accuracy": earned / (2 * answered) if answered else 0.0,
        "cw": cw,
        "cw_fields": cw_fields,
        "critical_misses": critical,
        "a_correct": a_correct,
        "parcels": len(per_parcel),
    }


def screening_grade(agg: dict[str, Any], per_parcel: dict[str, dict[str, FieldResult]]) -> bool:
    """Pre-registered rule from the kit: no critical miss, no CW on A, <=1 CW
    overall, accuracy >= 0.8."""
    cw_on_a = any(f["A"].cw for f in per_parcel.values() if "A" in f)
    return not agg["critical_misses"] and not cw_on_a and agg["cw"] <= 1 and agg["accuracy"] >= 0.8


def agreement(per_parcel: dict[str, dict[str, FieldResult]], hand: dict[str, dict[str, str]] | None) -> dict[str, Any]:
    """How often the automatic score matches a person's, per field."""
    if not hand:
        return {}
    by_field: dict[str, list[int]] = {f: [0, 0] for f in FIELDS}
    misses: list[str] = []
    for pid, fields in per_parcel.items():
        for fld, r in fields.items():
            raw = (hand.get(pid) or {}).get(fld)
            if raw is None:
                continue
            want = parse_hand_score(raw)
            by_field[fld][1] += 1
            if (r.auto_score, r.auto_cw) == want:
                by_field[fld][0] += 1
            else:
                misses.append(f"{pid}.{fld}: auto {FieldResult(r.auto_score, r.auto_cw).label()} / hand {raw}")
    return {
        "by_field": {f: f"{a}/{b}" for f, (a, b) in by_field.items() if b},
        "agree": sum(a for a, _ in by_field.values()),
        "total": sum(b for _, b in by_field.values()),
        "disagreements": misses,
    }


# --------------------------------------------------------------------------
# Loading runs (replay) and fetching them (live)
# --------------------------------------------------------------------------

def load_verdicts(files: list[Path]) -> dict[str, dict]:
    """Verdict text for saved /api/scorecard responses, from the real frontend
    module via node. {} when node isn't available (profile B/E/F then lack the
    verdict sentences and the report says so)."""
    if not files:
        return {}
    try:
        proc = subprocess.run(
            ["node", "--experimental-strip-types", "--no-warnings", str(VERDICT_SCRIPT), *map(str, files)],
            capture_output=True, text=True, timeout=60, check=True,
        )
        raw = json.loads(proc.stdout)
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError):
        return {}
    return {str(Path(k)): v for k, v in raw.items()}


def load_run_dir(run_dir: Path, key: dict) -> dict[str, dict[str, Any]]:
    """{pid: {'profile': dict|None, 'chat': dict|None, 'verdict': dict|None}}"""
    runs: dict[str, dict[str, Any]] = {}
    missing_verdicts: list[Path] = []
    for p in key["parcels"]:
        pid = p["id"]
        entry: dict[str, Any] = {"profile": None, "chat": None, "verdict": None}
        for surface in SURFACES:
            f = run_dir / f"{pid}.{surface}.json"
            if f.exists():
                entry[surface] = json.loads(f.read_text())
        v = run_dir / f"{pid}.verdict.json"
        if v.exists():
            entry["verdict"] = json.loads(v.read_text())
        elif entry["profile"] is not None:
            missing_verdicts.append(run_dir / f"{pid}.profile.json")
        runs[pid] = entry
    if missing_verdicts:
        got = load_verdicts(missing_verdicts)
        for p in missing_verdicts:
            pid = p.name.split(".")[0]
            runs[pid]["verdict"] = got.get(str(p))
            if runs[pid]["verdict"]:
                (run_dir / f"{pid}.verdict.json").write_text(json.dumps(runs[pid]["verdict"], indent=1))
    return runs


async def _fetch_profile(http: Any, base: str, address: str) -> dict:
    r = await http.get(f"{base}/api/scorecard", params={"address": address}, timeout=120.0)
    r.raise_for_status()
    return r.json()


async def _fetch_chat(http: Any, base: str, message: str) -> dict:
    """POST /chat with the address only, collect the SSE stream into one record."""
    out: dict[str, Any] = {"text": "", "error": None}
    plan = ctx = None
    done: dict = {}
    toks: list[str] = []
    t0 = time.monotonic()
    async with http.stream("POST", f"{base}/chat", json={"message": message, "history": []}, timeout=300.0) as resp:
        resp.raise_for_status()
        async for line in resp.aiter_lines():
            if not line.startswith("data:"):
                continue
            try:
                ev = json.loads(line[5:])
            except json.JSONDecodeError:
                continue
            t = ev.get("type")
            if t == "token":
                toks.append(ev.get("text", ""))
            elif t == "plan":
                plan = ev.get("plan")
            elif t == "context":
                ctx = ev.get("context")
            elif t == "error":
                out["error"] = ev.get("error")
            elif t == "done":
                done = ev
    plan = plan if isinstance(plan, dict) else {}
    ctx = ctx if isinstance(ctx, dict) else {}
    out.update(
        seconds=round(time.monotonic() - t0, 1),
        text="".join(toks),
        citation_warnings=done.get("citation_warnings"),
        plan_location=plan.get("location"),
        plan_sources=plan.get("sources"),
        context_zone=ctx.get("parcel_zoning"),
    )
    for k in ("truncated",):  # reported by the API once F4 ships
        if k in done:
            out[k] = done[k]
    return out


async def fetch_runs(base: str, key: dict, parcels: list[str], surfaces: list[str], raw_dir: Path) -> None:
    import httpx

    raw_dir.mkdir(parents=True, exist_ok=True)
    async with httpx.AsyncClient() as http:
        for p in key["parcels"]:
            if p["id"] not in parcels:
                continue
            if "profile" in surfaces:
                print(f"{p['id']} profile {p['address']} ...", flush=True)
                try:
                    data = await _fetch_profile(http, base, p["address"])
                    (raw_dir / f"{p['id']}.profile.json").write_text(json.dumps(data, indent=1))
                except Exception as exc:  # noqa: BLE001
                    print(f"  profile FAILED: {type(exc).__name__}: {exc}", file=sys.stderr)
            if "chat" in surfaces:
                print(f"{p['id']} chat {p['address']} ...", flush=True)
                try:
                    data = await _fetch_chat(http, base, build_prompt(key, p))
                    data.update(pid=p["id"], address=p["address"])
                    (raw_dir / f"{p['id']}.chat.json").write_text(json.dumps(data, indent=1))
                    if data["error"]:
                        print(f"  chat error: {data['error']}", file=sys.stderr)
                except Exception as exc:  # noqa: BLE001
                    print(f"  chat FAILED: {type(exc).__name__}: {exc}", file=sys.stderr)


# --------------------------------------------------------------------------
# Orchestration + report
# --------------------------------------------------------------------------

def score_run_dir(
    run_dir: Path, key: dict, surfaces: list[str], parcels: list[str] | None = None,
    manual: dict | None = None, manual_fields: str = "BEF",
) -> dict[str, Any]:
    runs = load_run_dir(run_dir, key)
    selected = [p for p in key["parcels"] if not parcels or p["id"] in parcels]
    report: dict[str, Any] = {
        "surfaces": {}, "resolution": {}, "truncation": {}, "manual_fields": manual_fields if manual else "",
        "forced_cells": (manual or {}).get("force", {}),
        "errored_runs": {},
        "provenance": {},
    }
    for surface in surfaces:
        per_parcel: dict[str, dict[str, FieldResult]] = {}
        n_scored = 0
        hand = (manual or {}).get("surfaces", {}).get(surface)
        for p in selected:
            run = runs[p["id"]]
            if surface == "chat" and run[surface] and run[surface].get("error"):
                # The API call failed (e.g. out of credit): there is no answer to score.
                report["errored_runs"].setdefault(surface, {})[p["id"]] = str(run[surface]["error"])[:120]
                continue
            res = score_parcel_surface(p, surface, run[surface], run["verdict"])
            if not res:
                continue
            forced = {c.split(".")[1] for c in (manual or {}).get("force", {}).get(surface, {}) if c.startswith(p["id"] + ".")}
            apply_manual(res, (hand or {}).get(p["id"]), manual_fields, forced)
            per_parcel[p["id"]] = res
            n_scored += len(p["scored"])
        agg = aggregate(per_parcel, n_scored)
        agg["screening_grade"] = screening_grade(agg, per_parcel)
        report["surfaces"][surface] = {
            "aggregate": agg,
            "fields": {pid: {f: _field_json(r) for f, r in fs.items()} for pid, fs in per_parcel.items()},
            "agreement": agreement(per_parcel, hand),
            "manual_cells": sum(1 for fs in per_parcel.values() for r in fs.values() if r.basis == "manual"),
        }
    if "profile" in surfaces and "chat" in surfaces:
        for p in selected:
            run = runs[p["id"]]
            if run["profile"] and run["chat"]:
                report["resolution"][p["id"]] = resolution_check(run["profile"], run["chat"])
    for p in selected:
        if runs[p["id"]]["chat"]:
            report["truncation"][p["id"]] = truncation_check(runs[p["id"]]["chat"])
            if report["truncation"][p["id"]].get("errored"):
                report["resolution"].pop(p["id"], None)
    if "profile" in surfaces:
        for p in selected:
            pc = provenance_check(p, runs[p["id"]]["profile"])
            if pc is not None:
                report["provenance"][p["id"]] = pc
    report["verdict_text_available"] = all(runs[p["id"]]["verdict"] for p in selected if runs[p["id"]]["profile"])
    return report


def _field_json(r: FieldResult) -> dict[str, Any]:
    return {
        "score": r.score, "cw": r.cw, "label": r.label(), "basis": r.basis,
        "auto": FieldResult(r.auto_score, r.auto_cw).label(), "detail": r.detail,
    }


def _pct(x: float) -> str:
    return f"{round(100 * x)}%"


def render_markdown(report: dict[str, Any], key: dict, meta: dict[str, Any]) -> str:
    L: list[str] = []
    L.append("# Parcel kit report")
    L.append("")
    L.append(f"Key `{key['version']}` · run {meta.get('date')} · code `{meta.get('git_sha') or 'unknown'}` · source: {meta.get('source')}")
    L.append("")
    L.append(f"> {key['note']}")
    L.append("")
    L.append("## Summary")
    L.append("")
    L.append("| Surface | Coverage | Accuracy | CW | Critical misses | A correct | Screening-grade |")
    L.append("|---|:-:|:-:|:-:|---|:-:|:-:|")
    for s, body in report["surfaces"].items():
        a = body["aggregate"]
        L.append(
            f"| {s} | {a['answered']}/{a['scored_fields']} = {_pct(a['coverage'])} | {a['points']}/{a['possible']} = {_pct(a['accuracy'])} "
            f"| {a['cw']} | {', '.join(a['critical_misses']) or 'none'} | {a['a_correct']}/{a['parcels']} | {'yes' if a['screening_grade'] else 'no'} |"
        )
    L.append("")
    if report["manual_fields"]:
        L.append(f"Fields `{report['manual_fields']}` use hand scores where the hand-scores file has them; all other cells are automatic. "
                 "Hand-scored cells: " + ", ".join(f"{s} {b['manual_cells']}" for s, b in report["surfaces"].items()) + ".")
    else:
        L.append("All cells are automatic (no hand-scores file).")
    for surf, cells in report["forced_cells"].items():
        for cell, why in cells.items():
            L.append(f"- Hand score forced outside `{report['manual_fields']}` on {surf} {cell}: {why}")
    for surf, runs_err in report["errored_runs"].items():
        for pid, msg in runs_err.items():
            L.append(f"- **{surf} {pid} NOT SCORED: the API call failed** ({msg}). Counts below exclude it; re-run that parcel.")
    if not report["verdict_text_available"]:
        L.append("")
        L.append("**Verdict text was unavailable (node missing?), so Profile B/E/F lack the verdict sentences.**")
    L.append("")
    for s, body in report["surfaces"].items():
        L.append(f"## {s}: field scores")
        L.append("")
        L.append("| Parcel | " + " | ".join(FIELDS) + " |")
        L.append("|---|" + "|".join([":-:"] * len(FIELDS)) + "|")
        for pid, fs in body["fields"].items():
            cells = []
            for f in FIELDS:
                c = fs.get(f)
                cells.append("" if c is None else c["label"] + ("*" if c["basis"] == "manual" else ""))
            L.append(f"| {pid} | " + " | ".join(cells) + " |")
        L.append("")
        L.append("`*` = hand score; `CW` = confident-wrong; `NP` = no claim.")
        ag = body["agreement"]
        if ag:
            L.append("")
            L.append(f"Automatic vs hand scores: **{ag['agree']}/{ag['total']}** cells agree ({', '.join(f'{f} {v}' for f, v in ag['by_field'].items())}).")
            if ag["disagreements"]:
                L.append("")
                L.append("<details><summary>Disagreements</summary>\n")
                L.extend(f"- {d}" for d in ag["disagreements"])
                L.append("\n</details>")
        L.append("")
    if report["resolution"]:
        L.append("## Parcel resolution (chat vs Profile)")
        L.append("")
        L.append("| Parcel | Profile PIN | PIN chat cited | Match | Point gap (ft) | Same community area |")
        L.append("|---|---|---|:-:|:-:|:-:|")
        for pid, r in report["resolution"].items():
            L.append(
                f"| {pid} | {r.get('profile_pin') or ''} | {r.get('chat_pin_in_text') or ''} | {_tf(r.get('chat_pin_matches'))} "
                f"| {r.get('point_gap_ft', '')} | {_tf(r.get('community_area_matches'))} |"
            )
        L.append("")
    if report["truncation"]:
        L.append("## Chat answer completeness")
        L.append("")
        L.append("| Parcel | Chars | Reaches item 6 | Ends cleanly | Cut-off notice | Silently cut off | Field names leaked |")
        L.append("|---|--:|:-:|:-:|:-:|:-:|---|")
        for pid, t in report["truncation"].items():
            L.append(
                f"| {pid} | {t['chars']} | {_tf(t['item6_present'])} | {_tf(t['ends_cleanly'])} "
                f"| {'yes' if t.get('notice_shown') else ''} | {'YES' if t.get('silently_cut_off') else ''} "
                f"| {', '.join(t.get('field_name_leaks') or [])} |"
            )
        L.append("")
    if report["provenance"]:
        tot = sum(v["required"] for v in report["provenance"].values())
        ok = sum(v["dated"] for v in report["provenance"].values())
        L.append("## Provenance (Profile: district, standards and expected overlays with a dated source)")
        L.append("")
        sd = sum(v.get("source_dated", 0) for v in report["provenance"].values())
        L.append(f"**{ok}/{tot}** stated facts carry a dated source; **{sd}/{tot}** carry a date the source itself gives "
                 "(an edit/effective date or the code's current-through date). The rest carry only the date we queried them.")
        L.append("")
        L.append("| Parcel | Facts | With any date | Source-side date | Missing |")
        L.append("|---|--:|--:|--:|---|")
        for pid, v in report["provenance"].items():
            L.append(f"| {pid} | {v['required']} | {v['dated']} | {v.get('source_dated', 0)} | {', '.join(v['missing'])} |")
        L.append("")
    L.append("## Per-cell detail")
    L.append("")
    for s, body in report["surfaces"].items():
        L.append(f"### {s}")
        L.append("")
        for pid, fs in body["fields"].items():
            for f, c in fs.items():
                L.append(f"- **{pid}.{f}** {c['label']} (auto {c['auto']}, {c['basis']}) — {c['detail']}")
        L.append("")
    return "\n".join(L)


def _tf(v: Any) -> str:
    return "" if v is None else ("yes" if v else "NO")


def git_sha() -> str | None:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, check=True,
                              cwd=Path(__file__).resolve().parent.parent).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def append_history(report: dict[str, Any], key: dict, notes: str) -> None:
    surf = report["surfaces"]
    headline = " | ".join(
        f"{s} cov {_pct(b['aggregate']['coverage'])} acc {_pct(b['aggregate']['accuracy'])} CW {b['aggregate']['cw']} A {b['aggregate']['a_correct']}/{b['aggregate']['parcels']}"
        for s, b in surf.items()
    )
    n = max((b["aggregate"]["parcels"] for b in surf.values()), default=0)
    with HISTORY_CSV.open("a", newline="") as f:
        csv.writer(f, lineterminator="\n").writerow([date.today().isoformat(), "parcel_kit", git_sha() or "", n, headline, notes])


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--full", metavar="BASE_URL", help="run the real system at this URL, then score it")
    src.add_argument("--replay", metavar="DIR", help="score saved runs (P<n>.profile.json / P<n>.chat.json) without network")
    ap.add_argument("--out-dir", help="where to write parcel_kit.md/.json (and raw runs for --full); default eval/results/<today>")
    ap.add_argument("--parcels", help="comma-separated ids, e.g. P2,P5 (default all)")
    ap.add_argument("--surfaces", default="profile,chat", help="comma-separated: profile,chat")
    ap.add_argument("--manual", metavar="FILE", help="hand-scores JSON (default for --replay: manual_scores.json in the replay dir)")
    ap.add_argument("--manual-fields", default="BEF", help="fields the hand scores override (default BEF); others are scored automatically")
    ap.add_argument("--history", metavar="NOTES", help="append a row to eval/results/history.csv with these notes")
    args = ap.parse_args(argv)

    key = load_key()
    surfaces = [s for s in args.surfaces.split(",") if s in SURFACES]
    parcels = args.parcels.split(",") if args.parcels else None
    out_dir = Path(args.out_dir) if args.out_dir else Path(__file__).resolve().parent / "results" / date.today().isoformat()
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.full:
        run_dir = out_dir / "parcel_kit_raw"
        asyncio.run(fetch_runs(args.full, key, parcels or [p["id"] for p in key["parcels"]], surfaces, run_dir))
        source = f"live run against {args.full}"
    else:
        run_dir = Path(args.replay)
        source = f"replay of {run_dir}"

    manual_path = Path(args.manual) if args.manual else (run_dir / "manual_scores.json" if args.replay else None)
    manual = json.loads(manual_path.read_text()) if manual_path and manual_path.exists() else None
    if manual:
        source += f"; hand scores: {manual.get('label', manual_path.name)}"

    report = score_run_dir(run_dir, key, surfaces, parcels, manual, args.manual_fields)
    meta = {"date": datetime.now(timezone.utc).date().isoformat(), "git_sha": git_sha(), "source": source}
    report["meta"] = {**meta, "key_version": key["version"]}
    md = render_markdown(report, key, meta)
    (out_dir / "parcel_kit.md").write_text(md + "\n")
    (out_dir / "parcel_kit.json").write_text(json.dumps(report, indent=1) + "\n")
    print(md.split("## Per-cell detail")[0])
    print(f"wrote {out_dir / 'parcel_kit.md'} and parcel_kit.json")
    if args.history:
        append_history(report, key, args.history)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
