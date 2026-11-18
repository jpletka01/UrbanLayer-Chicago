"""Chat answer audit: run question + follow-up pairs through the local /chat, score them deterministically.

Questions, gold answers and source expectations live in ``eval/chat_audit_questions.json``. Every model call the
backend makes is logged in its own ``llm_calls`` table, so the spend is read from there (``backend.llm.estimate_cost``)
and a hard cap stops the run before it is crossed.

    # spend (needs a local backend on --base with RATE_LIMIT_ANON_DAY=0 RATE_LIMIT_ANON_HOUR=0)
    PYTHONPATH=. python -m eval.chat_audit pairs --ids restaurant_rm6_wrightwood,bar_b1_wilson --cap 1.00
    PYTHONPATH=. python -m eval.chat_audit router --ids all --cap 1.00        # router plans only (~$0.004 each)
    # free
    PYTHONPATH=. python -m eval.chat_audit score                              # score the recorded runs
    PYTHONPATH=. python -m eval.chat_audit retrieval                          # router query vs district-aware query
    PYTHONPATH=. python -m eval.chat_audit historical --db path/to/chicago.db # over-fetch in stored conversations
    PYTHONPATH=. python -m eval.chat_audit spend                              # what the llm_calls table says was spent
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sqlite3
import sys
import time
import uuid
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

QUESTIONS = ROOT / "eval" / "chat_audit_questions.json"
OUT = ROOT / "eval" / "results" / "2026-11-12-chat-audit"
RUNS = OUT / "runs.jsonl"
ROUTER_RUNS = OUT / "router_runs.jsonl"
AREA_FEEDS = {"crime_api", "311_api", "permits_api", "violations_api", "business_api", "vacant_buildings_api",
              "food_inspections_api"}


def load_questions() -> dict[str, dict]:
    return {q["id"]: q for q in json.loads(QUESTIONS.read_text())["queries"]}


# --------------------------------------------------------------------------- spend (read from llm_calls)

def _db_path() -> Path:
    from backend.config import get_settings

    return Path(get_settings().db_path)


def spend_rows(since_id: int = 0) -> list[dict]:
    from backend.llm import estimate_cost

    con = sqlite3.connect(f"file:{_db_path()}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    try:
        rows = con.execute(
            "SELECT id, request_group, conversation_id, phase, model, input_tokens, output_tokens, cache_read_tokens, "
            "cache_create_tokens, created_at FROM llm_calls WHERE id > ? ORDER BY id", (since_id,)).fetchall()
    except sqlite3.OperationalError:
        con.close()
        return []
    out = []
    for r in rows:
        d = dict(r)
        d["cost"] = estimate_cost(d["model"], d["input_tokens"] or 0, d["output_tokens"] or 0,
                                  d["cache_read_tokens"] or 0, d["cache_create_tokens"] or 0)
        out.append(d)
    con.close()
    return out


def max_call_id() -> int:
    rows = spend_rows()
    return rows[-1]["id"] if rows else 0


def total_spent() -> float:
    return sum(r["cost"] for r in spend_rows())


# --------------------------------------------------------------------------- one /chat turn over SSE

async def chat_turn(http, base: str, message: str, history: list[dict], conversation_id: str | None) -> dict:
    rec: dict[str, Any] = {"message": message, "plan": None, "context": None, "answer": "", "turn_summary": None,
                           "citation_warnings": [], "truncated": None, "timings": {}, "error": None}
    parts: list[str] = []
    body = {"message": message, "history": history}
    if conversation_id:
        body["conversation_id"] = conversation_id
    async with http.stream("POST", f"{base}/chat", json=body, timeout=180.0) as resp:
        if resp.status_code != 200:
            rec["error"] = f"HTTP {resp.status_code}: {(await resp.aread())[:300]!r}"
            return rec
        async for line in resp.aiter_lines():
            if not line.startswith("data:"):
                continue
            try:
                evt = json.loads(line[5:].strip())
            except json.JSONDecodeError:
                continue
            t = evt.get("type")
            if t == "plan":
                rec["plan"] = evt.get("plan")
            elif t == "context":
                rec["context"] = evt.get("context")
            elif t == "token":
                parts.append(evt.get("text") or "")
            elif t == "turn_summary":
                rec["turn_summary"] = evt.get("turn_summary")
            elif t == "error":
                rec["error"] = evt.get("error")
            elif t == "done":
                rec["citation_warnings"] = evt.get("citation_warnings") or []
                rec["truncated"] = evt.get("truncated")
                rec["timings"] = evt.get("timings") or {}
    rec["answer"] = "".join(parts)
    return rec


async def _new_conversation(qid: str) -> str:
    from backend import db

    conv_id = f"conv_audit_{qid}_{uuid.uuid4().hex[:6]}"
    await db.create_conversation(conv_id, f"audit {qid}")
    return conv_id


async def _persist(conv_id: str, user: str, turn: dict) -> None:
    """What the full chat does after a turn: store the pair, the assistant row carrying its turn summary."""
    from backend import db

    await db.save_messages(conv_id, [
        {"role": "user", "content": user},
        {"role": "assistant", "content": turn["answer"], "plan": turn["plan"], "summary": turn["turn_summary"]},
    ])


def _turn_cost(since_id: int) -> tuple[float, list[dict]]:
    rows = spend_rows(since_id)
    return sum(r["cost"] for r in rows), [{k: r[k] for k in ("phase", "model", "input_tokens", "output_tokens",
                                                              "cache_read_tokens", "cache_create_tokens", "cost")} for r in rows]


def _log_budget(line: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with (OUT / "budget_log.md").open("a") as f:
        f.write(line + "\n")


async def run_pairs(ids: list[str], base: str, cap: float, reserve: float, single: bool) -> None:

    from backend import db

    qs = load_questions()
    await db.init_db()
    OUT.mkdir(parents=True, exist_ok=True)
    try:
        await _run_pairs(ids, base, cap, reserve, single, qs)
    finally:
        await db.close_db()  # an open aiosqlite connection keeps the process alive


async def _run_pairs(ids, base, cap, reserve, single, qs) -> None:
    import httpx

    async with httpx.AsyncClient() as http:
        for qid in ids:
            q = qs[qid]
            spent = total_spent()
            if spent + reserve > cap:
                print(f"STOP before {qid}: spent ${spent:.4f}, next pair reserve ${reserve:.2f}, cap ${cap:.2f}")
                return
            conv_id = await _new_conversation(qid)
            mark = max_call_id()
            t1 = await chat_turn(http, base, q["question"], [], conv_id)
            c1, calls1 = _turn_cost(mark)
            t1.update(cost=c1, calls=calls1)
            _log_budget(f"| {time.strftime('%H:%M')} | {qid} | turn 1 | {q['question']} | ${c1:.4f} | ${total_spent():.4f} |")
            print(f"{qid} turn1 ${c1:.4f} total ${total_spent():.4f} err={t1['error']}")
            t2 = None
            fq = q.get("followup")
            if fq and not single and not t1["error"] and total_spent() + reserve / 2 <= cap:
                await _persist(conv_id, q["question"], t1)
                mark = max_call_id()
                history = [{"role": "user", "content": q["question"]}, {"role": "assistant", "content": t1["answer"]}]
                t2 = await chat_turn(http, base, fq["question"], history, conv_id)
                c2, calls2 = _turn_cost(mark)
                t2.update(cost=c2, calls=calls2)
                _log_budget(f"| {time.strftime('%H:%M')} | {qid} | follow-up | {fq['question']} | ${c2:.4f} | ${total_spent():.4f} |")
                print(f"{qid} turn2 ${c2:.4f} total ${total_spent():.4f} err={t2['error']}")
            record = json.dumps({"id": qid, "conversation_id": conv_id, "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                                 "turn1": t1, "turn2": t2}, ensure_ascii=False)
            # Walk Score's links carry the API account's domain; the results are committed to a public repo.
            record = re.sub(r"utm_source=[^&\"]+", "utm_source=REDACTED", record)
            with RUNS.open("a") as f:
                f.write(record + "\n")


async def run_router(ids: list[str], cap: float) -> None:
    from backend import db

    # tracked_create logs each call to llm_calls through backend.db; without an open connection the calls are not
    # logged and the cap below cannot see them (2026-11-12: 54 router calls went unlogged this way).
    await db.init_db()
    try:
        await _run_router(ids, cap)
    finally:
        await db.close_db()


async def _run_router(ids: list[str], cap: float) -> None:
    from backend.router import route

    qs = load_questions()
    OUT.mkdir(parents=True, exist_ok=True)
    for qid in ids:
        if total_spent() + 0.01 > cap:
            print(f"STOP before {qid}: spent ${total_spent():.4f}")
            return
        mark = max_call_id()
        try:
            plan = (await route(qs[qid]["question"], request_group=str(uuid.uuid4()),
                                conversation_id="conv_audit_router")).model_dump(mode="json")
            err = None
        except Exception as exc:  # a bad JSON plan is a finding, not a crash
            plan, err = None, f"{type(exc).__name__}: {exc}"
        cost, _ = _turn_cost(mark)
        with ROUTER_RUNS.open("a") as f:
            f.write(json.dumps({"id": qid, "plan": plan, "error": err, "cost": cost}) + "\n")
        print(f"{qid:34} ${cost:.4f} total ${total_spent():.4f} {(plan or {}).get('sources')}")
    _log_budget(f"| {time.strftime('%H:%M')} | router-only x{len(ids)} | | | | ${total_spent():.4f} |")


# --------------------------------------------------------------------------- deterministic scoring

TOPICS = {
    "crime": r"\[data:crime\]|\bcrimes?\b|arrest rate|\bthefts?\b|\bbattery\b",
    "311": r"\[data:311\]|\b311\b",
    "permits": r"\[data:permits\]|\bpermits? (were |have been )?(issued|activity)|estimated construction cost|renovation/alteration permits",
    "business": r"\[data:business\]|business licen|active businesses|Retail Food Establishment",
    "violations": r"\[data:violations\]|building violations?|code violations?",
    "vacant": r"\[data:vacant_buildings\]|vacant[- ]building",
    "food": r"\[data:food_inspections\]|food inspections?",
    "aro": r"affordable (housing )?(projects|units)|\bARO\b|Affordable Requirements",
    "flood": r"\bflood|\bFEMA\b",
    "adu": r"\bADUs?\b|coach house|additional dwelling unit|conversion unit",
    "walkscore": r"Walk Score|Transit Score|Bike Score",
    "demographics": r"median (household )?income|\bpopulation\b|poverty",
    "incentives": r"\bTIF\b|Opportunity Zone|Enterprise Zone|\bNMTC\b|\bQCT\b",
    "property_value": r"assessed value|sale price|sold for|tax bill|property tax",
    "overlay_landmark": r"[Ll]andmark|National Register|historic district|Lakefront",
    "transit": r"\bCTA\b|\bMetra\b|transit-served|\bTOD\b",
    "schools": r"attendance (area|boundary)|\bCPS\b|elementary school|high school",
    "brownfield": r"brownfield|superfund",
}

NO_RE = re.compile(r"^\W*no\b|\bnot (be )?(permitted|allowed)|\bisn'?t (permitted|allowed)|\bprohibited|\bcannot\b|\bcan'?t\b|"
                   r"\bnot (a )?(by[- ]right|listed|available)|\bdoes not (allow|permit)|\bnot an? (allowed|permitted)", re.I)
YES_RE = re.compile(r"^\W*yes\b|\b(is|are) (permitted|allowed)|permitted by[- ]right|allowed by[- ]right|\blikely allow|"
                    r"\byou can (open|build|put|run|add)", re.I)
SPECIAL_RE = re.compile(r"special use", re.I)
CANT_RE = re.compile(r"can'?t (tell|confirm|determine|say|predict|locate|find)|cannot (tell|confirm|determine|say|predict|locate|find)|"
                     r"unable to|don'?t have|do not have|not (in|available in) (the|my)|no (data|record)|isn'?t (available|in)|"
                     r"not able to|couldn'?t (find|locate)|could not (find|locate)|outside|doesn'?t (allow|include|break)|can'?t break|"
                     r"no way to", re.I)
DECLINE_RE = re.compile(r"only (help|answer|provide)|can only|outside (of )?(Chicago|the City|my)|not (able|designed)|"
                        r"I (focus|cover|specialize)|I'?m (a|an) .{0,40}(assistant|tool)|can'?t help with|isn'?t something I", re.I)
CONDITIONAL_RE = re.compile(r"\bonly\b|\bwith(in)? (limits|conditions|approval)|subject to|\bbut\b|\bprovided\b|\bif\b|"
                            r"\brequires?\b|\bneeds?\b|\bcapped\b|\bup to\b", re.I)
FIELD_RE = re.compile(r"`?\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\b`?")
FIELD_OK = {"e_g"}


def body_of(answer: str) -> str:
    """The model's own text: drop the appended sources block and the cut-off notice."""
    for cut in ("\n---\n**Sources", "\n\n---\n*This answer was cut off"):
        i = answer.find(cut)
        if i != -1:
            answer = answer[:i]
    return answer


def first_sentence(text: str) -> str:
    # The first prose line: answers often open with a markdown heading ("## Opening a Bar at ..."), which is a title,
    # not the conclusion.
    t = ""
    for line in text.splitlines():
        if line.strip() and not line.lstrip().startswith("#") and not re.fullmatch(r"\s*[-*_]{3,}\s*", line):
            t = re.sub(r"[*_>`]", "", line).strip()
            break
    m = re.search(r"(?<!\b[A-Z])(?<!\bSt)(?<!\bAve)(?<!\bN)(?<!\bW)(?<!\bS)(?<!\bE)(?<!\d)[.!?](\s|$)", t)
    return t[: m.end()].strip() if m else t



def polarity(s: str) -> set[str]:
    out = set()
    if NO_RE.search(s):
        out.add("no")
    elif YES_RE.search(s):
        out.add("yes")
    if SPECIAL_RE.search(s):
        out.add("special_use")
    if CANT_RE.search(s):
        out.add("cant_tell")
    if DECLINE_RE.search(s):
        out.add("decline")
    if CONDITIONAL_RE.search(s):
        out.add("conditional")
    return out


def first_sentence_agrees(gold: str, s: str, plan: dict | None) -> bool | None:
    p = polarity(s)
    if gold == "yes":
        return "yes" in p and "no" not in p
    if gold == "no":
        return "no" in p and "yes" not in p
    if gold == "special_use":
        return "special_use" in p
    if gold == "conditional":
        return bool(p & {"yes", "special_use", "conditional"}) and not ({"no"} == p)
    if gold == "cant_tell":
        return bool(p & {"cant_tell", "decline", "no"})
    if gold == "decline":
        return bool(p & {"decline", "cant_tell"}) or (plan or {}).get("intent") == "clarification_needed"
    if gold == "clarify":
        return (plan or {}).get("intent") == "clarification_needed" or s.rstrip().endswith("?")
    return None  # "info": no polarity to agree with


def _sec_prefix(s: str) -> str | None:
    m = re.match(r"(\d+[A-Z]?-\d+-\d{2})", s.replace("§", "").strip())
    return m.group(1) if m else None


def score_answer(q: dict, gold: dict, rel_topics: list[str], sources: dict, turn: dict) -> dict:
    ans = turn.get("answer") or ""
    body = body_of(ans)
    plan = turn.get("plan") or {}
    ctx = turn.get("context") or {}
    fs = first_sentence(body)
    must_ok = all(re.search(p, body, re.I) for p in gold.get("must", []))
    wrong_hits = [p for p in gold.get("wrong", []) if re.search(p, body, re.I)]
    agrees = first_sentence_agrees(gold["conclusion"], fs, plan)
    # Opens "yes" and later says the use is not permitted (the 2026-11-12 restaurant answer). A lead to read: the
    # later "not permitted" may be about a different use.
    rest = body[len(fs):] if body.lstrip("*# ").startswith(fs[:20]) else body
    mixed = "yes" in polarity(fs) and bool(re.search(r"not (be )?(permitted|allowed)|prohibited", rest, re.I))
    conclusion_ok = must_ok and not wrong_hits and (agrees is not False)
    fetched = set(plan.get("sources") or [])
    over = sorted(fetched & set(sources.get("not_needed", [])))
    missing = sorted(set(sources.get("need", [])) - fetched)
    topics = sorted(t for t, rx in TOPICS.items() if re.search(rx, body))
    filler = sorted(set(topics) - set(rel_topics) - {"zoning"})
    stripped = re.sub(r"\[data:[a-z_0-9]+\]|https?://\S+", "", body)
    fields = sorted({f.strip("`") for f in FIELD_RE.findall(stripped)} - FIELD_OK)
    chunks = ctx.get("code_chunks") or []
    cited_n = sorted({int(n) for n in re.findall(r"\[(\d{1,2})\]", body)})
    cited_secs = [chunks[n - 1].get("section") for n in cited_n if 0 < n <= len(chunks)]
    retrieved = [c.get("section") for c in chunks]
    gold_pref = {p for p in (_sec_prefix(b) for b in gold.get("basis", [])) if p}
    gold_retrieved = sorted({s for s in retrieved if s and any(s.startswith(p) for p in gold_pref)})
    cited_off = sorted({s for s in cited_secs if s and gold_pref and not any(s.startswith(p) for p in gold_pref)})
    return {
        "first_sentence": fs[:240], "first_sentence_agrees": agrees, "mixed_conclusion": mixed,
        "must_ok": must_ok, "wrong_hits": wrong_hits, "conclusion_ok": conclusion_ok,
        "intent": plan.get("intent"), "workflow": plan.get("workflow_hint"), "search_query": plan.get("search_query"),
        "fetched": sorted(fetched), "over_fetch": over, "under_fetch": missing,
        "topics": topics, "filler_topics": filler, "leaked_fields": fields,
        "retrieved_sections": retrieved, "gold_prefixes": sorted(gold_pref), "gold_retrieved": gold_retrieved,
        "cited_sections": cited_secs, "cited_off_gold": cited_off, "citation_warnings": turn.get("citation_warnings") or [],
        "truncated": bool(turn.get("truncated")), "words": len(re.findall(r"\w+", body)),
        "pin": plan.get("location", {}).get("pin") if plan else None, "cost": turn.get("cost"),
        "error": turn.get("error"),
    }


def score_runs() -> dict:
    qs = load_questions()
    out = []
    for line in RUNS.read_text().splitlines():
        r = json.loads(line)
        q = qs[r["id"]]
        s1 = score_answer(q, q["gold"], q["relevant_topics"], q["sources"], r["turn1"])
        s2 = None
        if r.get("turn2") and q.get("followup"):
            fq = q["followup"]
            s2 = score_answer(q, fq["gold"], sorted(set(fq["relevant_topics"]) | set(q["relevant_topics"])), fq["sources"], r["turn2"])
            body2 = body_of(r["turn2"]["answer"])
            s2["carry_ok"] = all(re.search(p, body2, re.I) for p in fq.get("carry_re", []))
            s2["same_pin"] = (s1["pin"] == s2["pin"]) if s1["pin"] else None
            plan2 = r["turn2"].get("plan") or {}
            s2["router_saw_address"] = bool((plan2.get("location") or {}).get("raw"))
            s2["parcel_data_refetched"] = bool((r["turn2"].get("context") or {}).get("parcel_zoning"))
            s2["turn1_chunk_sections"] = s1["retrieved_sections"]
            # [N] indexes this turn's chunk list, but the earlier answer the model reads used the same numbers for
            # turn 1's list. A number cited in both turns that now points at a different section is a drift lead.
            n1 = {int(n) for n in re.findall(r"\[(\d{1,2})\]", body_of(r["turn1"]["answer"]))}
            n2 = {int(n) for n in re.findall(r"\[(\d{1,2})\]", body2)}
            sec1, sec2 = s1["retrieved_sections"], s2["retrieved_sections"]
            s2["index_drift"] = sorted(f"[{n}] {sec1[n-1]} -> {sec2[n-1]}" for n in n1 & n2
                                       if n <= len(sec1) and n <= len(sec2) and sec1[n - 1] != sec2[n - 1])
        out.append({"id": r["id"], "category": q["category"], "question": q["question"],
                    "followup": (q.get("followup") or {}).get("question") if r.get("turn2") else None,
                    "gold": q["gold"]["conclusion"], "turn1": s1, "turn2": s2})
    rows = sorted({r["id"]: r for r in out}.values(), key=lambda x: x["id"])  # last run of an id wins
    (OUT / "scores.json").write_text(json.dumps(rows, indent=1, ensure_ascii=False) + "\n")
    _write_scores_md(rows)
    return {"n": len(rows)}


def _write_scores_md(rows: list[dict]) -> None:
    def yn(v):
        return "—" if v is None else ("yes" if v else "**no**")

    lines = ["# Chat audit scores (deterministic)", "",
             "| id | turn | gold | 1st sentence agrees | conclusion ok | mixed | over-fetch | under-fetch | filler | leaked fields | gold sec retrieved | cited off-gold | words | $ |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|---:|---:|"]
    for r in rows:
        for turn in ("turn1", "turn2"):
            s = r[turn]
            if not s:
                continue
            extra = ""
            if turn == "turn2":
                extra = f" carry={yn(s.get('carry_ok'))} same_pin={yn(s.get('same_pin'))}"
            lines.append(
                f"| {r['id']} | {turn[-1]}{extra} | {r['gold'] if turn == 'turn1' else ''} | {yn(s['first_sentence_agrees'])} | "
                f"{yn(s['conclusion_ok'])} | {'**yes**' if s['mixed_conclusion'] else ''} | {', '.join(s['over_fetch'])} | "
                f"{', '.join(s['under_fetch'])} | {', '.join(s['filler_topics'])} | {', '.join(s['leaked_fields'])} | "
                f"{', '.join(s['gold_retrieved']) or ('none' if s['gold_prefixes'] else '')} | {', '.join(s['cited_off_gold'])} | "
                f"{s['words']} | {s['cost'] or 0:.3f} |")
    (OUT / "scores.md").write_text("\n".join(lines) + "\n")


def score_router() -> list[dict]:
    qs = load_questions()
    rows = {}
    for line in ROUTER_RUNS.read_text().splitlines():
        r = json.loads(line)
        q = qs[r["id"]]
        plan = r.get("plan") or {}
        fetched = set(plan.get("sources") or [])
        rows[r["id"]] = {"id": r["id"], "category": q["category"], "intent": plan.get("intent"),
                         "workflow": plan.get("workflow_hint"), "fetched": sorted(fetched),
                         "over_fetch": sorted(fetched & set(q["sources"]["not_needed"])),
                         "under_fetch": sorted(set(q["sources"]["need"]) - fetched),
                         "search_query": plan.get("search_query"), "error": r.get("error")}
    out = sorted(rows.values(), key=lambda x: x["id"])
    (OUT / "router_scores.json").write_text(json.dumps(out, indent=1) + "\n")
    return out


# --------------------------------------------------------------------------- free: retrieval and stored plans

FAMILY_TABLE = {"R": "17-2-0200", "B": "17-3-0200", "C": "17-3-0200", "D": "17-4-0200", "M": "17-5-0200"}
FAMILY_BULK = {"R": "17-2-0300", "B": "17-3-0400", "C": "17-3-0400", "D": "17-4-0400", "M": "17-5-0400"}
USE_TABLES = set(FAMILY_TABLE.values()) | {"17-6-0200", "17-6-0400"}
DISTRICT_RE = re.compile(r"\b(RS|RT|RM|B|C|M|D[CXRS]?|PD)[- ]?(\d(?:\.\d)?)(?:-(\d+(?:\.\d)?))?\b")


def _family(district: str) -> str | None:
    d = district.upper()
    if d.startswith(("RS", "RT", "RM")):
        return "R"
    return d[0] if d[:1] in FAMILY_TABLE else None


def _named_districts(text: str | None) -> set[str]:
    return {m.group(1) + m.group(2) for m in DISTRICT_RE.finditer(text or "")}


async def retrieval_check() -> list[dict]:
    """Parcel questions with a recorded router plan. The router writes the search query before the parcel's district
    is known, so it either names no district or guesses one. Compare what that query retrieves with a query that
    names the district (known after the zoning lookup): is the district's own table there, how many other districts'
    use tables crowd the top 5, and is a specific gold section (not a use or bulk table) there."""
    from backend.retrieval.vector_search import semantic_search

    qs = load_questions()
    planned: dict[str, str] = {}
    for path in (ROUTER_RUNS, RUNS):
        if not path.exists():
            continue
        for line in path.read_text().splitlines():
            r = json.loads(line)
            plan = r.get("plan") or (r.get("turn1") or {}).get("plan") or {}
            if plan.get("search_query"):
                planned[r["id"]] = plan["search_query"]
    out = []
    for qid, q in qs.items():
        fam = _family(q.get("district") or "")
        if q["category"] not in ("parcel_use", "parcel_trick", "parcel_bulk") or not fam or qid not in planned:
            continue
        bulk = q["category"] == "parcel_bulk"
        own = (FAMILY_BULK if bulk else FAMILY_TABLE)[fam]
        specific = {p for p in (_sec_prefix(b) for b in q["gold"]["basis"]) if p} - {own[:7]} - {t[:7] for t in USE_TABLES} - {"17-17-01"}
        district_code = q["district"].split()[0]
        aware = (f"{district_code} bulk and density standards floor area ratio height lot area per unit" if bulk
                 else f"{district_code} use table allowed uses permitted special uses")
        named = _named_districts(planned[qid])
        actual = re.sub(r"-.*", "", district_code.replace("-", "", 1)) if district_code[:2] in ("RS", "RT", "RM") else district_code.split("-")[0]
        row = {"id": qid, "district": q["district"], "own_table": own, "specific_gold": sorted(specific),
               "router_named_districts": sorted(named),
               "router_guessed_wrong_district": bool(named) and not any(n.startswith(actual) for n in named)}
        for label, query in (("router", planned[qid]), ("district_aware", aware)):
            secs = [c.section for c in await semantic_search(query, top_k=5)]
            row[label] = {"query": query, "sections": secs, "own_table": own in secs,
                          "other_use_tables": sorted({s for s in secs if s in USE_TABLES and s != own}),
                          "specific_gold": sorted({s for s in secs if any(s.startswith(p) for p in specific)})}
        out.append(row)
        print(f"{qid:30} {q['district']:7} named={sorted(named)!s:12} own: router={row['router']['own_table']!s:5} "
              f"aware={row['district_aware']['own_table']!s:5} other: {len(row['router']['other_use_tables'])}->"
              f"{len(row['district_aware']['other_use_tables'])} specific: {row['router']['specific_gold']}->{row['district_aware']['specific_gold']}")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "retrieval_check.json").write_text(json.dumps(out, indent=1) + "\n")
    return out


PARCEL_Q_RE = re.compile(r"\b(can|could|would) i\b|allowed|zon(e|ing)|\bbuild\b|\bFAR\b|units?|height|coach house|demolish|"
                         r"what can i|constraint", re.I)
ADDRESS_RE = re.compile(r"\b\d{2,5}\s+[NSEW]\.?\s+\w+", re.I)


def historical(dbs: list[str]) -> dict:
    """Over-fetch in plans already stored in local conversations (no model calls)."""
    seen, rows = set(), []
    for path in dbs:
        con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        for conv, pos, plan_json, q in con.execute(
                "SELECT m.conversation_id, m.position, m.plan_json, (SELECT content FROM messages u WHERE "
                "u.conversation_id = m.conversation_id AND u.position = m.position - 1) FROM messages m "
                "WHERE m.role = 'assistant' AND m.plan_json IS NOT NULL"):
            key = (q or "").strip().lower()
            if not key or key in seen:
                continue
            seen.add(key)
            plan = json.loads(plan_json)
            parcel_scoped = bool(ADDRESS_RE.search(q)) and bool(PARCEL_Q_RE.search(q)) and not re.search(
                r"crime|311|permits? (issued|near)|violations|going on|tell me about|what do you know|what can you tell", q, re.I)
            area = sorted(set(plan.get("sources") or []) & AREA_FEEDS)
            rows.append({"question": q, "workflow": plan.get("workflow_hint"), "sources": plan.get("sources"),
                         "parcel_scoped_use_or_bulk": parcel_scoped, "area_feeds": area})
        con.close()
    scoped = [r for r in rows if r["parcel_scoped_use_or_bulk"]]
    summary = {"unique_questions": len(rows), "parcel_scoped_use_or_bulk": len(scoped),
               "with_area_feeds": sum(1 for r in scoped if r["area_feeds"]),
               "area_feed_counts": {f: sum(1 for r in scoped if f in r["area_feeds"]) for f in sorted(AREA_FEEDS)},
               "rows": rows}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "historical_plans.json").write_text(json.dumps(summary, indent=1, ensure_ascii=False) + "\n")
    print({k: v for k, v in summary.items() if k != "rows"})
    return summary


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["pairs", "router", "score", "retrieval", "historical", "spend"])
    ap.add_argument("--ids", default="")
    ap.add_argument("--base", default="http://localhost:8011")
    ap.add_argument("--cap", type=float, default=1.00)
    ap.add_argument("--reserve", type=float, default=0.14, help="stop a pair when spent + this would pass the cap")
    ap.add_argument("--single", action="store_true", help="turn 1 only")
    ap.add_argument("--db", action="append", default=[])
    a = ap.parse_args()
    qs = load_questions()
    ids = list(qs) if a.ids == "all" else [i for i in a.ids.split(",") if i]
    if a.cmd == "pairs":
        asyncio.run(run_pairs(ids, a.base, a.cap, a.reserve, a.single))
    elif a.cmd == "router":
        asyncio.run(run_router(ids, a.cap))
    elif a.cmd == "score":
        if RUNS.exists():
            print(score_runs())
        if ROUTER_RUNS.exists():
            print(len(score_router()), "router plans scored")
    elif a.cmd == "retrieval":
        asyncio.run(retrieval_check())
    elif a.cmd == "historical":
        historical(a.db)
    elif a.cmd == "spend":
        rows = spend_rows()
        by = {}
        for r in rows:
            by.setdefault(r["phase"], [0, 0.0])
            by[r["phase"]][0] += 1
            by[r["phase"]][1] += r["cost"]
        print({k: (n, round(c, 4)) for k, (n, c) in by.items()}, "total", round(sum(r["cost"] for r in rows), 4))


if __name__ == "__main__":
    main()
