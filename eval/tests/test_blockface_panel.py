import pytest

from eval import blockface_panel as bp


@pytest.mark.parametrize("address, key", [
    ("1747 N KEDZIE AVE", ("N", "KEDZIE AVE", 1700, "odd")),
    ("1746 N KEDZIE AVE", ("N", "KEDZIE AVE", 1700, "even")),
    ("4900 W  BELMONT AVE ", ("W", "BELMONT AVE", 4900, "even")),
    ("~1747 N KEDZIE AVE", None),  # the builder's approximate tier is left out
    ("KEDZIE AVE", None),
    (None, None),
])
def test_face_key(address, key):
    assert bp.face_key(address) == key


@pytest.mark.parametrize("cls, chars, units, why", [
    ("2-11", {"char_apts": "Three", "pin_num_cards": "1"}, 3, "char_apts"),
    ("2-03", {"char_apts": "None", "pin_num_cards": "1"}, 1, "char_apts_none"),
    ("2-03", {"char_apts": "None", "pin_num_cards": "2"}, None, "multi_card"),  # a second building: unknown
    ("2-11", {"pin_num_cards": "1"}, None, "char_apts_missing"),
    ("2-99", None, 2, "class_multi_unit"),
    ("3-15", None, 2, "class_multi_unit"),
    ("1-00", None, 0, "class_vacant"),
    ("EX", None, None, "no_record"),
])
def test_units_from_record(cls, chars, units, why):
    assert bp.units_from_record(cls, chars) == (units, why)


def test_judge_face_gate_and_rule():
    assert bp.judge_face([2, 2, 2, 1, 1])["meets_60"] is True  # 3 of 5 = 60%
    assert bp.judge_face([2, 2, 1, 1, 1])["meets_60"] is False
    j = bp.judge_face([2, 2, 2, None, 1, 1, 1, 1, 1, 1])  # 90% known: computable
    assert j["computable"] and j["coverage"] == 0.9
    j = bp.judge_face([2, 2, 2, None, None, 1, 1, 1, 1, 1])  # 80% known: not judged
    assert not j["computable"] and j["meets_60"] is None
