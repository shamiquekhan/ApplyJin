"""TokenCounter abstraction: baseline counting, truncation, model fallback."""

from __future__ import annotations

from applyjin.inference.tokens import (
    ApproximateTokenCounter,
    TokenCounter,
    counter_for_model,
    estimate_tokens,
)


def test_approximate_counter_counts_word_and_punctuation_units():
    counter = ApproximateTokenCounter()
    assert counter.count("") == 0
    assert counter.count("Python APIs") == estimate_tokens("Python APIs") >= 2
    assert isinstance(counter, TokenCounter)


def test_truncate_never_exceeds_the_token_budget():
    counter = ApproximateTokenCounter()
    text = "Build fast APIs with Python and Rust. " * 50
    budget = 25
    truncated = counter.truncate(text, budget)
    assert 0 < len(truncated) <= len(text)
    assert counter.count(truncated) <= budget
    # in-budget text is returned untouched
    assert counter.truncate("short text", budget) == "short text"
    assert counter.truncate(text, 0) == ""


def test_truncate_preserves_prefix_content():
    counter = ApproximateTokenCounter()
    text = "alpha beta gamma delta epsilon zeta eta theta"
    truncated = counter.truncate(text, 4)
    assert truncated.split() == ["alpha", "beta", "gamma", "delta"]


def test_counter_for_model_falls_back_to_the_baseline():
    counter = counter_for_model("definitely/not-a-real-model")
    assert isinstance(counter, ApproximateTokenCounter)
    assert counter_for_model(None) is not None
