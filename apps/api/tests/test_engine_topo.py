"""Topological ordering for the run engine.

We import the private helper directly because it has no I/O — perfect unit-test
shape and the only correctness-critical bit of pure logic in the engine.
"""

from __future__ import annotations

from ouroboros_api.orchestrator.engine import _topological_order


def test_topo_simple_chain() -> None:
    graph = {
        "nodes": [{"id": "a"}, {"id": "b"}, {"id": "c"}],
        "edges": [{"source": "a", "target": "b"}, {"source": "b", "target": "c"}],
    }
    assert _topological_order(graph) == ["a", "b", "c"]


def test_topo_diamond() -> None:
    graph = {
        "nodes": [{"id": "a"}, {"id": "b"}, {"id": "c"}, {"id": "d"}],
        "edges": [
            {"source": "a", "target": "b"},
            {"source": "a", "target": "c"},
            {"source": "b", "target": "d"},
            {"source": "c", "target": "d"},
        ],
    }
    order = _topological_order(graph)
    assert order.index("a") < order.index("b")
    assert order.index("a") < order.index("c")
    assert order.index("b") < order.index("d")
    assert order.index("c") < order.index("d")


def test_topo_ignores_failure_loop_edges() -> None:
    """Edges with `tests.failed` conditions are retry loops, not graph deps."""
    graph = {
        "nodes": [{"id": "build"}, {"id": "test"}, {"id": "ship"}],
        "edges": [
            {"source": "build", "target": "test"},
            {"source": "test", "target": "ship"},
            {"source": "test", "target": "build", "condition": "tests.failed"},
        ],
    }
    order = _topological_order(graph)
    assert order == ["build", "test", "ship"]


def test_topo_falls_back_for_cycles() -> None:
    graph = {
        "nodes": [{"id": "a"}, {"id": "b"}],
        "edges": [{"source": "a", "target": "b"}, {"source": "b", "target": "a"}],
    }
    order = _topological_order(graph)
    assert set(order) == {"a", "b"}
