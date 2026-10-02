"""Sources for a chat answer that the model does not write.

Two problems, one cause: the model writes the answer AND its sources. The kit's
baseline answers carried 18 URLs across 7 answers, including American Legal links
whose ids the model composed (one id, ``0-0-0-563405``, was cited for two different
sections) and Legistar links nobody gave it. A reader clicking one lands somewhere
that doesn't say what the answer claims.

- ``UrlGuard`` filters the streamed answer: a link or bare URL survives only if we
  supplied it (the provenance map, an overlay's link, a coverage note, the PD PDF);
  any other is dropped and a markdown link keeps its visible label.
- ``build_sources_footer`` appends the sources deterministically: the dated provenance
  entries for the parcel data the answer was given, and the code chunks it cited
  (``[N]``), each with the code's current-through date.
"""

from __future__ import annotations

import re
from typing import Any, Iterator

_LINK = re.compile(r"\[([^\[\]]*)\]\(\s*<?(https?://[^)\s>]+)>?[^)]*\)")
_OPEN_LINK = re.compile(r"\[([^\[\]]*)\]\(\s*<?https?://[^)\s>]*$")
_BARE = re.compile(r"https?://[^\s)>\]\"']+")
_MAX_HOLD = 600  # never stall the stream on a stray "[" or "http"
_TRAILING = ".,;:!?)"


def _norm(url: str) -> str:
    url = url.strip().rstrip(_TRAILING)
    url = url.split("#", 1)[0]
    return url[:-1] if url.endswith("/") else url


def allowed_urls(context: Any) -> set[str]:
    """Every URL we put in front of the model or the reader for this turn."""
    from backend.retrieval.coverage_notes import OFFICIAL_LETTER_URL

    urls: set[str] = {OFFICIAL_LETTER_URL}
    zoning = getattr(context, "parcel_zoning", None)
    if zoning is not None:
        for u in (getattr(zoning, "zoning_map_url", None), getattr(zoning, "clerk_url", None)):
            if u:
                urls.add(u)
    regulatory = getattr(context, "regulatory", None)
    for ov in (regulatory.overlays if regulatory else []):
        if ov.link:
            urls.add(ov.link)
    ward = getattr(getattr(context, "neighborhood", None), "ward", None)
    if ward is not None and getattr(ward, "website", None):
        urls.add(ward.website)
    pin = getattr(context, "parcel_pin", None)
    if pin:
        urls.add(f"https://www.cookcountyassessor.com/pin/{pin}")
    prop = getattr(context, "property", None)
    for u in (getattr(prop, "report_url", None),):
        if u:
            urls.add(u)
    for note in (getattr(context, "coverage_notes", None) or []):
        if note.get("link"):
            urls.add(note["link"])
    return {_norm(u) for u in urls}


class UrlGuard:
    """Streaming filter: ``feed`` each token, ``flush`` at the end. Text is released
    as soon as no link can still be forming; a half-written ``[label](https://...``
    is held until it closes, then kept (allowed URL) or reduced to its label."""

    def __init__(self, allowed: set[str]):
        self._allowed = {_norm(u) for u in allowed}
        self._buf = ""
        self.dropped: list[str] = []

    # --- cleaning -------------------------------------------------------------------------
    def _ok(self, url: str) -> bool:
        return _norm(url) in self._allowed

    def _clean(self, text: str) -> str:
        out: list[str] = []
        pos = 0
        for m in _LINK.finditer(text):
            out.append(self._clean_bare(text[pos : m.start()]))
            if self._ok(m.group(2)):
                out.append(m.group(0))
            else:
                self.dropped.append(m.group(2))
                out.append(m.group(1))  # keep the words, lose the invented target
            pos = m.end()
        out.append(self._clean_bare(text[pos:]))
        return "".join(out)

    def _clean_bare(self, text: str) -> str:
        def repl(m: re.Match) -> str:
            url = m.group(0)
            if self._ok(url):
                return url
            core = url.rstrip(_TRAILING)
            self.dropped.append(core)
            return url[len(core):]  # keep the sentence's own punctuation

        return _BARE.sub(repl, text)

    # --- streaming ---------------------------------------------------------------------------
    def _hold_from(self) -> int:
        """Index in the buffer from which text may still change (0 = hold everything)."""
        buf = self._buf
        hold = len(buf)
        # a "[" with no closing "]" after it: a label in progress
        lb = buf.rfind("[")
        if lb != -1 and "]" not in buf[lb:]:
            hold = min(hold, lb)
        # a label that just closed: "(" may be about to follow, making it a link
        if buf.endswith("]"):
            start = buf.rfind("[")
            if start != -1:
                hold = min(hold, start)
        # "](" with no closing ")": a link target in progress; hold from its label
        lp = buf.rfind("](")
        if lp != -1 and ")" not in buf[lp:]:
            start = buf.rfind("[", 0, lp)
            hold = min(hold, start if start != -1 else lp)
        # a bare URL (or a prefix of "http") at the very end
        tail = re.search(r"(?:h|ht|htt|http|https|https:|https:/|https?://\S*)$", buf)
        if tail:
            i = tail.start()
            before = buf[i - 1] if i else " "
            in_link_target = before in "(<" and buf[max(0, i - 2) : i] in ("](", "(<")  # "[x](" / "[x](<": the link rule holds it
            if not in_link_target and (i == 0 or before in " \n\t(<*\"'"):
                hold = min(hold, i)
        return hold

    def feed(self, chunk: str) -> str:
        self._buf += chunk
        hold = self._hold_from()
        if len(self._buf) - hold > _MAX_HOLD:  # something odd: stop holding
            hold = len(self._buf)
        emit, self._buf = self._buf[:hold], self._buf[hold:]
        return self._clean(emit)

    def flush(self) -> str:
        buf, self._buf = self._buf, ""
        # A link still open when the stream ends (cut off mid-URL) can't be verified:
        # keep its words, drop the dangling target.
        buf = _OPEN_LINK.sub(lambda m: m.group(1), buf)
        return self._clean(buf)

    def filter(self, tokens: Iterator[str]) -> Iterator[str]:
        for t in tokens:
            piece = self.feed(t)
            if piece:
                yield piece
        tail = self.flush()
        if tail:
            yield tail


# --- the footer -----------------------------------------------------------------------------

_BULK = ("zoning.far", "zoning.max_height", "zoning.min_lot_area_per_unit")


def _src(entry: dict) -> str:
    bits = []
    if entry.get("effective_date"):
        bits.append(f"effective {entry['effective_date']}")
    if entry.get("as_of"):
        bits.append(f"record updated {entry['as_of']}")
    if entry.get("query_date"):
        bits.append(f"queried {entry['query_date']}")
    return ", ".join(bits)


def build_sources_footer(provenance: dict[str, dict], cited_chunks: list[tuple[int, Any]], code_through: str | None) -> str:
    """Markdown 'Sources' block, or '' when there is nothing to list. ``cited_chunks`` is
    [(N, CodeChunk)] for the ``[N]`` markers the answer actually used."""
    lines: list[str] = []
    d = provenance.get("zoning.district")
    if d:
        rec = f", ordinance {d['record_id']}" if d.get("record_id") else ""
        lines.append(f"- **{d['label']}**: {d['source']}{rec} ({_src(d)})")
    bulk = [provenance[k] for k in _BULK if k in provenance]
    if bulk:
        what = " / ".join(e["label"].split(" for ")[0].lower() for e in bulk)
        secs = " / ".join(f"§{e['section']}" for e in bulk)
        thru = f", code current through {bulk[0]['as_of']}" if bulk[0].get("as_of") else ""
        lines.append(f"- **Standards** ({what}): Municipal Code {secs}{thru}")
    for key, e in provenance.items():
        if key.startswith("overlay."):
            link = f" — [source]({e['url']})" if e.get("url") else ""
            lines.append(f"- **{e['label']}**: {e['source']}{link}")
    ident = provenance.get("parcel.identity")
    if ident:
        link = f" — [assessor record]({ident['url']})" if ident.get("url") else ""
        lines.append(f"- **{ident['label']}**: {ident['source']}{link}")
    for key in ("property.land_sqft", "property.bldg_sqft"):
        if key in provenance:
            lines.append(f"- **{provenance[key]['label']}**: {provenance[key]['source']}")
    for n, chunk in cited_chunks:
        thru = f" (code current through {code_through})" if code_through else ""
        title = f" — {chunk.section_title}" if getattr(chunk, "section_title", None) else ""
        lines.append(f"- [{n}] Municipal Code §{chunk.section}{title}{thru}")
    if not lines:
        return ""
    return "\n\n---\n**Sources for the parcel data used**\n" + "\n".join(lines) + "\n"


def cited_chunks(answer: str, code_chunks: list[Any]) -> list[tuple[int, Any]]:
    """[(N, chunk)] for each distinct ``[N]`` marker in the answer that points at a real chunk."""
    seen: list[int] = []
    for m in re.finditer(r"\[(\d+)\]", answer):
        n = int(m.group(1))
        if 1 <= n <= len(code_chunks) and n not in seen:
            seen.append(n)
    return [(n, code_chunks[n - 1]) for n in sorted(seen)]
