"""Held-out quality gate for the offline WS2 PR4 filing reader.

The panel contains only hand-labelled structured facts, never real PDF or OCR text.
It measures the drafting reader; publication still requires a separate human review.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


MIN_PANEL_ROWS = 30
MIN_HELD_OUT_ROWS = 10
PRECISION_FLOOR = 0.95
RECALL_FLOOR = 0.60


@dataclass(frozen=True)
class FieldValue:
    value: str
    page: int
    unit: str | None = None
    source: str | None = None  # attachment role the page belongs to


@dataclass(frozen=True)
class Evaluation:
    expected: int
    emitted: int
    matched: int
    wrong_value: int
    wrong_page: int
    wrong_unit: int

    @property
    def precision(self) -> float:
        return self.matched / self.emitted if self.emitted else 0.0

    @property
    def recall(self) -> float:
        return self.matched / self.expected if self.expected else 0.0

    @property
    def passes(self) -> bool:
        return (
            self.expected > 0
            and self.precision >= PRECISION_FLOOR
            and self.recall >= RECALL_FLOOR
            and not (self.wrong_value or self.wrong_page or self.wrong_unit)
        )


def evaluate(expected: dict[str, FieldValue], emitted: dict[str, FieldValue]) -> Evaluation:
    """Score an extraction by exact value/page/unit agreement.

    An omitted expected field lowers recall; an unexpected emitted field lowers
    precision.  A page (or attachment) or unit mismatch is separately counted and blocks release
    even if another field happens to make aggregate precision look acceptable.
    """
    matched = wrong_value = wrong_page = wrong_unit = 0
    for field_id, actual in emitted.items():
        label = expected.get(field_id)
        if label is None or actual.value != label.value:
            wrong_value += 1
            continue
        if actual.page != label.page or actual.source != label.source:
            wrong_page += 1
            continue
        if actual.unit != label.unit:
            wrong_unit += 1
            continue
        matched += 1
    return Evaluation(
        expected=len(expected), emitted=len(emitted), matched=matched,
        wrong_value=wrong_value, wrong_page=wrong_page, wrong_unit=wrong_unit,
    )


def panel_passes(rows: Iterable[Evaluation], *, panel_size: int, held_out_size: int) -> bool:
    """Apply the fixed sample and held-out split requirements to aggregate scores."""
    scores = list(rows)
    if panel_size < MIN_PANEL_ROWS or held_out_size < MIN_HELD_OUT_ROWS or len(scores) != held_out_size:
        return False
    total = Evaluation(
        expected=sum(row.expected for row in scores), emitted=sum(row.emitted for row in scores),
        matched=sum(row.matched for row in scores), wrong_value=sum(row.wrong_value for row in scores),
        wrong_page=sum(row.wrong_page for row in scores), wrong_unit=sum(row.wrong_unit for row in scores),
    )
    return total.passes
