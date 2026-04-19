"""Token + cost accounting helpers."""

from __future__ import annotations


def estimate_cost_usd(
    tokens_in: int, tokens_out: int, input_per_mtok: float | None, output_per_mtok: float | None
) -> float:
    inp = (input_per_mtok or 0.0) * tokens_in / 1_000_000
    out = (output_per_mtok or 0.0) * tokens_out / 1_000_000
    return round(inp + out, 6)
