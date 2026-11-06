"""Validated, metadata-only hand-review artifact for WS2 PR4.

``backend/pending_filing_details.json`` is the only thing the Profile may ever
show about an applicant's proposal.  Each entry is keyed by lifecycle id and
names the exact Clerk record and attachments a human read, with a page citation
for every value.  The offline reader may *draft* values; only an entry whose
``method`` is ``hand_reviewed`` is valid here.

``current_details`` is the request-path join: an entry is served only when the
current pending record and its live attachment metadata (URL, file name and
type) are exactly the ones reviewed.  A same-URL replacement of a PDF cannot be
detected on the request path (no download there); the monthly review re-hashes.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import urlparse

DETAILS_FILE = Path(__file__).resolve().parent.parent / "pending_filing_details.json"
SCHEMA_VERSION = 2
FIELD_IDS = frozenset({"from_district", "to_district", "lot_area", "dwelling_units", "height", "far", "parking"})
# Every number needs its unit on the page; districts and FAR are unitless by definition.
FIELD_UNITS = {"lot_area": "sq ft", "height": "ft", "parking": "spaces", "dwelling_units": None,
               "far": None, "from_district": None, "to_district": None}
ROLE_TYPES = {"ordinance": "Legislation", "narrative": "Exhibits"}
_SHA256 = re.compile(r"^[a-f0-9]{64}$")
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_NUMBER = re.compile(r"^\d+(?:\.\d+)?$")


def _attachment_problems(lifecycle: str, role: str, item: object) -> list[str]:
    if role not in ROLE_TYPES:
        return [f"{lifecycle}: unknown attachment role {role}"]
    if not isinstance(item, dict):
        return [f"{lifecycle}: {role} attachment not an object"]
    problems: list[str] = []
    name = str(item.get("file_name", ""))
    source = urlparse(str(item.get("url", "")))
    if source.scheme != "https" or not source.hostname or not name or "eds" in name.lower() or "application" in name.lower():
        problems.append(f"{lifecycle}: invalid {role} attachment identity")
    if item.get("type") != ROLE_TYPES[role]:
        problems.append(f"{lifecycle}: {role} attachment type must be {ROLE_TYPES[role]}")
    if not _SHA256.fullmatch(str(item.get("sha256", ""))):
        problems.append(f"{lifecycle}: invalid {role} sha256")
    return problems


def validate_artifact(data: object) -> list[str]:
    if not isinstance(data, dict) or data.get("schema_version") != SCHEMA_VERSION:
        return [f"schema_version must be {SCHEMA_VERSION}"]
    details = data.get("details")
    if not isinstance(details, dict):
        return ["details must be an object"]
    problems: list[str] = []
    for lifecycle, item in details.items():
        if not isinstance(item, dict):
            problems.append(f"{lifecycle}: not an object")
            continue
        for key in ("reviewed_record", "matter_id", "reviewed_on", "reviewed_by", "attachments", "fields"):
            if not item.get(key):
                problems.append(f"{lifecycle}: missing {key}")
        if item.get("method") != "hand_reviewed":
            problems.append(f"{lifecycle}: method must be hand_reviewed")
        if not _DATE.fullmatch(str(item.get("reviewed_on", ""))):
            problems.append(f"{lifecycle}: reviewed_on must be YYYY-MM-DD")
        attachments = item.get("attachments")
        if not isinstance(attachments, dict):
            problems.append(f"{lifecycle}: attachments must be an object")
            continue
        for role, attachment in attachments.items():
            problems += _attachment_problems(lifecycle, role, attachment)
        fields = item.get("fields")
        if not isinstance(fields, list):
            problems.append(f"{lifecycle}: fields must be a list")
            continue
        seen: set[str] = set()
        for field in fields:
            if (not isinstance(field, dict) or field.get("id") not in FIELD_IDS or not isinstance(field.get("value"), str)
                    or not field["value"] or type(field.get("page")) is not int or field["page"] < 1
                    or field.get("source") not in attachments):
                problems.append(f"{lifecycle}: invalid cited field")
                continue
            if field["id"] in seen:
                problems.append(f"{lifecycle}: duplicate field {field['id']}")
            seen.add(field["id"])
            if field.get("unit") != FIELD_UNITS[field["id"]]:
                problems.append(f"{lifecycle}: wrong unit for {field['id']}")
            if field["id"] not in {"from_district", "to_district"} and not _NUMBER.fullmatch(field["value"]):
                problems.append(f"{lifecycle}: {field['id']} must be a plain number")
            expected_source = "ordinance" if field["id"] in {"from_district", "to_district"} else "narrative"
            if field["source"] != expected_source:
                problems.append(f"{lifecycle}: {field['id']} must cite the {expected_source}")
    return problems


def load_details(path: Path = DETAILS_FILE) -> dict[str, dict]:
    """Valid entries or nothing: one malformed entry withholds the whole artifact."""
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError):
        return {}
    return {} if validate_artifact(data) else data["details"]


def current_details(lifecycle: str, record_number: str, attachments: list[dict], *,
                    details: dict[str, dict] | None = None) -> dict | None:
    """The reviewed entry for this lifecycle iff it reviewed the current record and attachments.

    ``attachments`` are the live pending-store rows (``file_name``, ``url``, ``type``).
    """
    entry = (load_details() if details is None else details).get(lifecycle)
    if not entry or entry.get("reviewed_record") != record_number:
        return None
    live = {(a.get("url"), a.get("file_name"), a.get("type")) for a in attachments}
    for reviewed in entry["attachments"].values():
        if (reviewed["url"], reviewed["file_name"], reviewed["type"]) not in live:
            return None
    return entry
