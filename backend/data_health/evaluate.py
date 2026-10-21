"""Turn a probe result into a status. Pure: no network, no clock (``today`` is passed in).

States: ``ok``, ``warn``, ``alarm``, ``error`` (a service answered with an error or the
contract is broken), ``unknown`` (no date signal; the contract is still checked),
``frozen_ok`` and ``acked``.

Rules (WS6 plan §3.4):
- the worst of the date check and the contract check wins;
- a frozen source is ``frozen_ok`` until its publisher date changes, then ``alarm``;
- a transient probe failure is ``warn`` on one run and ``alarm`` on two in a row, which
  absorbs a network blip; a service error body is ``error`` at once;
- an unexpired ``ack`` turns a bad state into ``acked`` (amber, does not alarm); an expired
  one makes it ``alarm``;
- a source with a working fallback (``warns_only_while_ok``) can only warn.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Literal, Mapping

from backend.data_health.registry import SourceSpec

State = Literal["ok", "warn", "alarm", "error", "unknown", "frozen_ok", "acked"]

# Worse = higher. ``acked`` and ``frozen_ok`` are outcomes, never inputs to the worst-of.
_RANK = {"ok": 0, "frozen_ok": 0, "unknown": 1, "warn": 2, "alarm": 3, "error": 4}
ALERTING = frozenset({"alarm", "error"})
_GOOD = frozenset({"ok", "frozen_ok", "acked"})


@dataclass(frozen=True)
class Finding:
    level: Literal["warn", "alarm", "error"]
    text: str


class ProbeError(Exception):
    """A probe could not read its source. ``transient``: a timeout, 5xx or connection error
    (absorbed once). ``service``: the service answered with an error body or the wrong shape."""

    def __init__(self, kind: Literal["transient", "service"], text: str):
        super().__init__(text)
        self.kind = kind
        self.text = text


@dataclass
class ProbeResult:
    """What a probe read. Parsers fill the facts; ``evaluate`` judges them."""

    published: date | None = None        # the publisher touched it (rowsUpdatedAt, Last-Modified, editingInfo)
    content: date | None = None          # the data itself (max of a date column, a release year, current_through)
    content_year: int | None = None      # for year-lag comparison against ``reference_year``
    reference_year: int | None = None
    layer_name: str | None = None
    fields: tuple[str, ...] = ()
    count: int | None = None
    findings: list[Finding] = field(default_factory=list)
    error: ProbeError | None = None
    skipped: str | None = None           # the probe could not run here (no API key, no local file)
    info: str = ""
    requests: int = 0
    latency_ms: int = 0


@dataclass(frozen=True)
class Status:
    state: State
    reason: str
    age_days: int | None = None
    as_of: date | None = None
    basis: Literal["content", "published"] | None = None


def _worst(parts: list[tuple[str, str]]) -> tuple[str, list[str]]:
    state = max((p[0] for p in parts), key=_RANK.__getitem__, default="ok")
    return state, [text for st, text in parts if st != "ok" and text]


def contract_findings(spec: SourceSpec, probe: ProbeResult) -> list[Finding]:
    """The cheap structural contract: layer name, required fields, feature-count band."""
    c = spec.contract
    if c is None:
        return []
    out: list[Finding] = []
    if c.layer_name is not None and probe.layer_name is not None and probe.layer_name != c.layer_name:
        out.append(Finding("error", f"layer name is now {probe.layer_name!r}, expected {c.layer_name!r}"))
    if c.required_fields and probe.fields:
        have = {f.lower() for f in probe.fields}
        missing = [f for f in c.required_fields if f.lower() not in have]
        if missing:
            out.append(Finding("error", f"missing field(s): {', '.join(missing)}"))
    if c.count_band is not None and probe.count is not None:
        lo, hi = c.count_band
        if not lo <= probe.count <= hi:
            out.append(Finding("alarm", f"{probe.count:,} features, expected {lo:,} to {hi:,}"))
    return out


def _date_part(spec: SourceSpec, probe: ProbeResult, today: date) -> tuple[str, str, date | None, str | None, int | None]:
    """(state, reason, as_of, basis, age_days) for the freshness of the data."""
    c = spec.content
    # A year column judged against another source's latest year, in releases.
    if c is not None and c.reference and probe.content_year is not None:
        if probe.reference_year is None:
            return "unknown", f"latest year {probe.content_year}; the reference release could not be read", None, None, None
        lag = probe.reference_year - probe.content_year
        label = f"{probe.content_year} vs the latest release {probe.reference_year}"
        as_of = date(probe.content_year, 12, 31)
        if lag >= c.lag_alarm:
            return "alarm", f"{lag} releases behind ({label})", as_of, "content", (today - as_of).days
        if lag >= c.lag_warn:
            return "warn", f"{lag} release behind ({label})", as_of, "content", (today - as_of).days
        return "ok", "", as_of, "content", (today - as_of).days

    basis, as_of = (("content", probe.content) if probe.content else ("published", probe.published))
    if as_of is None:
        if spec.availability_only:
            return "ok", "", None, None, None
        if spec.contract is not None:
            return "unknown", "no date field on this source; its structure is checked", None, None, None
        return "unknown", "no date signal", None, None, None
    age = (today - as_of).days
    if spec.warn_days is None and spec.alarm_days is None:
        if spec.availability_only:
            return "ok", "", as_of, basis, age
        return "unknown", f"{basis} date {as_of} but no tolerance set", as_of, basis, age
    what = "newest data" if basis == "content" else "last updated by the publisher"
    if spec.alarm_days is not None and age > spec.alarm_days:
        return "alarm", f"{what} {as_of} is {age} days old (alarm after {spec.alarm_days})", as_of, basis, age
    if spec.warn_days is not None and age > spec.warn_days:
        return "warn", f"{what} {as_of} is {age} days old (warn after {spec.warn_days})", as_of, basis, age
    return "ok", "", as_of, basis, age


def evaluate(
    spec: SourceSpec,
    probe: ProbeResult | None,
    today: date,
    *,
    previous_error: bool = False,
    peers: Mapping[str, str] | None = None,
) -> Status:
    """Judge one source. ``previous_error``: the last run's probe failed too.
    ``peers``: other sources' states, for ``warns_only_while_ok``."""
    if probe is None:
        if spec.frozen:
            return Status("frozen_ok", f"frozen: {spec.frozen.label}")
        return Status("unknown", f"no probe yet. {spec.note}".strip())

    if probe.error is not None:
        if probe.error.kind == "service":
            state, text = "error", f"service error: {probe.error.text}"
        elif previous_error:
            state, text = "alarm", f"probe failed twice in a row: {probe.error.text}"
        else:
            state, text = "warn", f"probe failed (first run): {probe.error.text}"
        return _finish(spec, state, text, None, None, None, today, peers)

    if probe.skipped:
        return Status("unknown", f"not probed here: {probe.skipped}")

    parts: list[tuple[str, str]] = []
    as_of: date | None = None
    basis: str | None = None
    age: int | None = None

    if spec.frozen is not None:
        published = probe.published
        if published is not None and published.isoformat() != spec.frozen.as_of:
            parts.append(("alarm", f"frozen source changed: publisher date is {published}, we expect "
                                   f"{spec.frozen.as_of} ({spec.frozen.label}). Our 'frozen' label may now be wrong"))
        as_of, basis = published, "published"
        age = (today - published).days if published else None
        date_state = "frozen_ok" if not parts else "alarm"
    else:
        date_state, reason, as_of, basis, age = _date_part(spec, probe, today)
        parts.append((date_state, reason))

    for f in contract_findings(spec, probe) + probe.findings:
        parts.append((f.level, f.text))

    state, reasons = _worst(parts)
    if state == "ok" and spec.frozen is not None and date_state == "frozen_ok":
        state = "frozen_ok"
        reasons = [f"frozen: {spec.frozen.label}"]
    if probe.info:
        reasons.append(probe.info)
    return _finish(spec, state, "; ".join(reasons), as_of, basis, age, today, peers)


def _finish(spec, state, reason, as_of, basis, age, today, peers) -> Status:
    if state in ALERTING and spec.warns_only_while_ok:
        peer = (peers or {}).get(spec.warns_only_while_ok)
        if peer in _GOOD:
            state, reason = "warn", f"{reason} (capped at warn: {spec.warns_only_while_ok} is {peer})"
    ack = spec.ack
    if ack is not None and state in ("warn", "alarm", "error"):
        if today > ack.until:
            return Status("alarm", f"ack expired {ack.until}: {ack.reason} | was {state}: {reason}", age, as_of, basis)
        return Status("acked", f"acked until {ack.until} ({ack.owner}); was {state}: {reason} | {ack.reason}", age, as_of, basis)
    return Status(state, reason, age, as_of, basis)
