"""Cost estimator."""

from __future__ import annotations

from ouroboros_api.orchestrator.cost import estimate_cost_usd


def test_estimate_cost_zero_when_no_pricing() -> None:
    assert estimate_cost_usd(1000, 1000, None, None) == 0.0


def test_estimate_cost_basic_math() -> None:
    cost = estimate_cost_usd(1_000_000, 1_000_000, 3.0, 15.0)
    assert cost == 18.0


def test_estimate_cost_handles_partial_pricing() -> None:
    cost = estimate_cost_usd(2_000_000, 0, 1.5, None)
    assert cost == 3.0


def test_estimate_cost_rounds_to_six_places() -> None:
    cost = estimate_cost_usd(1, 1, 1.0, 1.0)
    assert cost == round(2 / 1_000_000, 6)
