"""The review packet is generated from the key, stays blind, and covers every judgment field."""

from eval import parcel_kit as k
from eval import review_packet as rp


def test_committed_packet_is_current():
    assert rp.OUT.read_text() == rp.render(), "run `python -m eval.review_packet`"


def test_packet_is_blind():
    text = rp.render().lower()
    for leak in ("urbanlayer", "confident-wrong", "profile", "research/"):
        assert leak not in text


def test_every_judgment_tag_exists_in_the_key():
    key = k.load_key()
    tags = {f"{p['id']}.{f}" for p in key["parcels"] for f in p["scored"]}
    assert set(rp.JUDGMENT) <= tags
    text = rp.render()
    for t in rp.JUDGMENT:
        assert f"**{t}**" in text
