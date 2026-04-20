"""Heuristic router: language detection + provider/model selection."""

from __future__ import annotations

from types import SimpleNamespace

from ouroboros_api.orchestrator.router import detect_language, pick_model
from ouroboros_api.seeds.agents import DEFAULT_AGENTS


def test_detect_language_from_file_extension_in_body() -> None:
    issue = {"title": "Bug", "body": "Crash in src/main.py when ..."}
    assert detect_language(issue) == "python"


def test_detect_language_from_label() -> None:
    issue = {"title": "x", "body": "x", "labels": ["typescript"]}
    assert detect_language(issue) == "typescript"


def test_detect_language_returns_none_when_no_signal() -> None:
    assert detect_language({"title": "x", "body": "x", "labels": []}) is None


def test_detect_language_handles_missing_issue() -> None:
    assert detect_language(None) is None


def _provider(pid: str, kind: str = "ollama", enabled: bool = True) -> SimpleNamespace:
    return SimpleNamespace(id=pid, kind=kind, enabled=enabled, config={}, base_url=None, api_key_secret_ref=None)


def _model(pid: str, mid: str) -> SimpleNamespace:
    return SimpleNamespace(provider_id=pid, model_id=mid, input_cost_per_mtok=0.0, output_cost_per_mtok=0.0)


def _seed_policy(role: str) -> dict:
    spec = next(agent for agent in DEFAULT_AGENTS if agent["role"] == role)
    return spec["model_policy"]


def test_pick_model_respects_fixed_policy() -> None:
    agent = SimpleNamespace(
        role="coder",
        model_policy={"kind": "fixed", "fixed_provider_id": "p1", "fixed_model_id": "qwen2.5-coder"},
    )
    providers = [_provider("p1"), _provider("p2", "anthropic")]
    models = {"p1": [_model("p1", "qwen2.5-coder"), _model("p1", "llama3")], "p2": [_model("p2", "claude-3-opus")]}
    out = pick_model(agent, providers, models, issue=None)
    assert out and out[0].id == "p1" and out[1].model_id == "qwen2.5-coder"


def test_pick_model_router_uses_language_hint() -> None:
    agent = SimpleNamespace(
        role="coder",
        model_policy={
            "kind": "router",
            "router_hints": {"language_map": {"python": {"prefer_kind": "anthropic", "model_hint": "sonnet"}}},
        },
    )
    providers = [_provider("p1", "ollama"), _provider("p2", "anthropic")]
    models = {"p1": [_model("p1", "llama3")], "p2": [_model("p2", "claude-3-5-sonnet")]}
    out = pick_model(agent, providers, models, issue={"title": "x", "body": "src/x.py"})
    assert out and out[0].kind == "anthropic" and "sonnet" in out[1].model_id


def test_pick_model_uses_planner_seed_policy_for_python_issue() -> None:
    agent = SimpleNamespace(role="planner", model_policy=_seed_policy("planner"))
    providers = [_provider("p1", "ollama"), _provider("p2", "anthropic")]
    models = {"p1": [_model("p1", "llama3")], "p2": [_model("p2", "claude-3-5-sonnet")]}

    out = pick_model(agent, providers, models, issue={"title": "x", "body": "src/foo.py"})

    assert out and out[0].kind == "anthropic" and "sonnet" in out[1].model_id


def test_pick_model_uses_coder_seed_policy_for_python_issue() -> None:
    agent = SimpleNamespace(role="coder", model_policy=_seed_policy("coder"))
    providers = [_provider("p1", "anthropic"), _provider("p2", "ollama")]
    models = {"p1": [_model("p1", "claude-3-5-sonnet")], "p2": [_model("p2", "qwen2.5-coder")]}

    out = pick_model(agent, providers, models, issue={"title": "x", "body": "src/foo.py"})

    assert out and out[0].kind == "ollama" and "qwen" in out[1].model_id


def test_pick_model_falls_back_to_first_enabled_provider() -> None:
    agent = SimpleNamespace(role="coder", model_policy={"kind": "router"})
    providers = [_provider("p1", "ollama")]
    models = {"p1": [_model("p1", "llama3")]}
    out = pick_model(agent, providers, models, issue=None)
    assert out and out[0].id == "p1"


def test_pick_model_returns_none_when_no_models() -> None:
    agent = SimpleNamespace(role="coder", model_policy={"kind": "router"})
    assert pick_model(agent, [_provider("p1")], {"p1": []}, issue=None) is None


def test_pick_model_per_run_override_wins_over_policy() -> None:
    agent = SimpleNamespace(
        role="coder",
        model_policy={"kind": "fixed", "fixed_provider_id": "p1", "fixed_model_id": "llama3"},
    )
    providers = [_provider("p1"), _provider("p2", "anthropic")]
    models = {"p1": [_model("p1", "llama3")], "p2": [_model("p2", "claude-3-opus")]}
    out = pick_model(
        agent,
        providers,
        models,
        issue=None,
        overrides={"coder": {"provider_id": "p2", "model_id": "claude-3-opus"}},
    )
    assert out and out[0].id == "p2" and out[1].model_id == "claude-3-opus"
