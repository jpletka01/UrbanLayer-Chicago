"""`POST /api/discovery/text-preview` — what the text compiler makes of a phrase, without searching.

The free-text box is a compiler (INV-5): rule-based, never a model, covering a few dozen
phrases. It silently drops what it does not recognize, so a phrase like "teardown in logan
square" compiles to no filters and, sent as a search, would return every parcel. This
endpoint lets the page ask the compiler first and say so instead of searching.

It runs only the compile half of the pipeline, `parse → merge`, the same calls `/search`
makes through `api._resolve`, and stops before the evaluator: no index is read, nothing is
ranked, nothing is cached. What it returns is therefore what the text contributes to a
search's canonical CQS. It is advisory for the page's gate and feedback; the evaluated
`response.cqs` stays the only source of what a search actually used (INV-4).
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from backend.discovery.compile_merge import merge
from backend.discovery.compile_text import parse
from backend.discovery.cqs import CqsFragment, DroppedInvalid, Predicate

# Same prefix as the other Discovery routes, so the production proxy already routes it.
router = APIRouter(prefix="/api/discovery", tags=["discovery"])

# A phrase, not a document: the compiler is regex-based and linear, but there is no reason to
# accept an unbounded body on an anonymous endpoint.
MAX_TEXT_CHARS = 500


class TextPreviewRequest(BaseModel):
    text: str = Field(default="", max_length=MAX_TEXT_CHARS)


class UnderstoodFilter(BaseModel):
    filterId: str
    predicate: Predicate


class TextPreviewResponse(BaseModel):
    # Filters the text compiles to after the same compile-time validation a search applies.
    understood: list[UnderstoodFilter]
    # Words the compiler did not recognize (stopwords excluded), in the order they appear.
    residual: list[str]
    # Compiled predicates the merge refused (unknown id, wrong kind, invalid, missing prerequisite).
    droppedInvalid: list[DroppedInvalid] = Field(default_factory=list)


@router.post("/text-preview", response_model=TextPreviewResponse)
def text_preview(req: TextPreviewRequest) -> TextPreviewResponse:
    text_frag = parse(req.text)
    cqs, dropped = merge(CqsFragment(), text_frag)
    return TextPreviewResponse(
        understood=[
            UnderstoodFilter(filterId=fid, predicate=a.predicate) for fid, a in cqs.filters.items()
        ],
        residual=list(cqs.meta.textResidual),
        droppedInvalid=dropped,
    )
