"""Validated, metadata-only hand-review artifact for WS2 PR4.

This loader is deliberately offline and not wired to the Profile yet.  It makes
the review contract testable before a gated serving integration exists.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import urlparse

DETAILS_FILE = Path(__file__).resolve().parent.parent / "pending_filing_details.json"
FIELD_IDS = frozenset({"from_district", "to_district", "lot_area", "dwelling_units", "height", "far", "parking"})
_SHA256 = re.compile(r"^[a-f0-9]{64}$")


def validate_artifact(data: object) -> list[str]:
    if not isinstance(data, dict) or data.get("schema_version") != 1:
        return ["schema_version must be 1"]
    details = data.get("details")
    if not isinstance(details, dict):
        return ["details must be an object"]
    problems: list[str] = []
    for lifecycle, item in details.items():
        if not isinstance(item, dict):
            problems.append(f"{lifecycle}: not an object")
            continue
        for key in ("reviewed_record", "matter_id", "attachment_url", "attachment_file_name", "sha256", "reviewed_on", "reviewed_by", "fields"):
            if not item.get(key):
                problems.append(f"{lifecycle}: missing {key}")
        if item.get("method") != "hand_reviewed":
            problems.append(f"{lifecycle}: method must be hand_reviewed")
        if not _SHA256.fullmatch(str(item.get("sha256", ""))):
            problems.append(f"{lifecycle}: invalid sha256")
        source = urlparse(str(item.get("attachment_url", "")))
        if source.scheme != "https" or not source.hostname or "eds" in str(item.get("attachment_file_name", "")).lower():
            problems.append(f"{lifecycle}: invalid attachment identity")
        fields = item.get("fields")
        if not isinstance(fields, list):
            problems.append(f"{lifecycle}: fields must be a list")
            continue
        seen: set[str] = set()
        for field in fields:
            if not isinstance(field, dict) or field.get("id") not in FIELD_IDS or not field.get("value") or type(field.get("page")) is not int or field["page"] < 1:
                problems.append(f"{lifecycle}: invalid cited field")
                continue
            if field["id"] in seen:
                problems.append(f"{lifecycle}: duplicate field {field['id']}")
            seen.add(field["id"])
            if field["id"] in {"lot_area", "height"} and not field.get("unit"):
                problems.append(f"{lifecycle}: missing unit for {field['id']}")
    return problems


def load_details(path: Path = DETAILS_FILE) -> dict[str, dict]:
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError):
        return {}
    return {} if validate_artifact(data) else data["details"]
