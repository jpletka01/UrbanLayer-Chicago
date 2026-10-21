"""The payload diff tool: additions pass, removals and changes fail (so a schema change can't silently move a v1 field)."""

from eval.provenance_diff import diff_maps


def test_added_fields_are_not_a_regression():
    old = {"a": {"label": "x", "as_of": None}}
    new = {"a": {"label": "x", "as_of": None, "tier": "official_record"}}
    d = diff_maps(old, new)
    assert d["added_fields"] == {"a": ["tier"]} and not (d["removed_fields"] or d["changed"] or d["removed_entries"])


def test_a_removed_or_changed_v1_field_is_reported():
    old = {"a": {"label": "x", "kind": "official_record", "note": None}, "b": {"label": "y"}}
    new = {"a": {"label": "x", "kind": "derived"}}
    d = diff_maps(old, new)
    assert d["changed"] == {"a": {"kind": ("official_record", "derived")}}
    assert d["removed_fields"] == {"a": ["note"]} and d["removed_entries"] == ["b"]
