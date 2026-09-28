import pytest

from backend.llm import estimate_cost


def test_list_prices():
    assert estimate_cost("claude-sonnet-4-6", 1_000_000, 1_000_000) == pytest.approx(18.0)
    assert estimate_cost("claude-haiku-4-5-20251001", 1_000_000, 1_000_000) == pytest.approx(6.0)


def test_cache_reads_and_writes_are_priced():
    # Sonnet input $3/M: reads at 0.1x, 5-minute writes at 1.25x.
    assert estimate_cost("claude-sonnet-4-6", 0, 0, cache_read_tokens=1_000_000) == pytest.approx(0.30)
    assert estimate_cost("claude-sonnet-4-6", 0, 0, cache_write_tokens=1_000_000) == pytest.approx(3.75)


def test_unknown_model_falls_back_to_sonnet_rates():
    assert estimate_cost("claude-unknown", 1_000_000, 0) == pytest.approx(3.0)
