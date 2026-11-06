"""Validated, metadata-only hand-review artifact for WS2 PR4.

This loader is deliberately offline and not wired to the Profile yet.  It makes
the review contract testable before a gated serving integration exists.
"""
from __future__ import annotations

import json
from pathlib import Path

DETAILS_FILE = Path(__file__).resolve().parent.parent / "pending_filing_details.json"
FIELD_IDS = frozenset({"from_district", "to_district", "lot_area", "dwelling_units", "height", "far", "parking"})


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
        fields = item.get("fields")
        if not isinstance(fields, list):
            problems.append(f"{lifecycle}: fields must be a list")
            continue
        for field in fields:
            if not isinstance(field, dict) or field.get("id") not in FIELD_IDS or not field.get("value") or not isinstance(field.get("page"), int):
                problems.append(f"{lifecycle}: invalid cited field")
    return problems


def load_details(path: Path = DETAILS_FILE) -> dict[str, dict]:
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError):
        return {}
    return {} if validate_artifact(data) else data["details"]
