"""Engine intervention queue: pause + resume + timeout."""

from __future__ import annotations

import asyncio

import pytest

from ouroboros_api.orchestrator.intervention import InterventionRegistry


@pytest.mark.asyncio
async def test_intervention_resolves_when_answered() -> None:
    reg = InterventionRegistry()
    await reg.register("i1")

    async def respond() -> None:
        await asyncio.sleep(0.05)
        await reg.answer("i1", {"text": "go"})

    task = asyncio.create_task(respond())
    answer = await reg.wait("i1", timeout=1.0)
    await task
    assert answer == {"text": "go"}


@pytest.mark.asyncio
async def test_intervention_times_out_when_unanswered() -> None:
    reg = InterventionRegistry()
    await reg.register("i2")
    answer = await reg.wait("i2", timeout=0.05)
    assert answer is None


@pytest.mark.asyncio
async def test_answer_unknown_intervention_is_noop() -> None:
    reg = InterventionRegistry()
    assert await reg.answer("nope", {"x": 1}) is False


@pytest.mark.asyncio
async def test_discard_removes_pending_entry() -> None:
    reg = InterventionRegistry()
    await reg.register("i3")
    await reg.discard("i3")
    assert await reg.wait("i3", timeout=0.01) is None
