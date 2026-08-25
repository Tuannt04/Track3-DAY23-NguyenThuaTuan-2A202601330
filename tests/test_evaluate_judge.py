"""Tests for evaluate_node's LLM-as-judge guards: timeout, fallback, and cost budget.

These don't need a real LLM API key — get_llm() is monkeypatched with fake/slow clients
so the guard logic itself is verified deterministically and fast.
"""

from __future__ import annotations

import time

from langgraph_agent_lab import nodes


class _FakeStructuredLLM:
    """Stands in for llm.with_structured_output(EvaluationVerdict)."""

    def __init__(self, verdict: str = "success", reasoning: str = "looks fine", delay: float = 0.0):
        self.verdict = verdict
        self.reasoning = reasoning
        self.delay = delay
        self.call_count = 0

    def invoke(self, _messages):
        self.call_count += 1
        if self.delay:
            time.sleep(self.delay)
        return nodes.EvaluationVerdict(verdict=self.verdict, reasoning=self.reasoning)


class _FakeLLM:
    def __init__(self, structured: _FakeStructuredLLM):
        self._structured = structured

    def with_structured_output(self, _model):
        return self._structured


def _base_state(**overrides):
    state = {
        "query": "Please lookup order status for order 12345",
        "tool_results": ["SUCCESS: request handled (reference REF-00001)."],
        "judge_call_count": 0,
    }
    state.update(overrides)
    return state


def test_evaluate_node_uses_real_judge_verdict(monkeypatch):
    """When the judge is healthy, its verdict drives evaluation_result and is logged."""
    fake_structured = _FakeStructuredLLM(verdict="needs_retry", reasoning="ambiguous result")
    monkeypatch.setattr(nodes, "get_llm", lambda: _FakeLLM(fake_structured))

    result = nodes.evaluate_node(_base_state())

    assert result["evaluation_result"] == "needs_retry"
    assert result["judge_call_count"] == 1
    assert fake_structured.call_count == 1
    event = result["events"][0]
    assert "needs_retry" in event["metadata"]["judge_note"]


def test_evaluate_node_falls_back_on_timeout(monkeypatch):
    """A judge call slower than JUDGE_TIMEOUT_SECONDS must not hang the graph."""
    slow_structured = _FakeStructuredLLM(verdict="needs_retry", delay=0.5)
    monkeypatch.setattr(nodes, "get_llm", lambda: _FakeLLM(slow_structured))
    monkeypatch.setattr(nodes, "JUDGE_TIMEOUT_SECONDS", 0.05)

    started = time.perf_counter()
    result = nodes.evaluate_node(_base_state())
    elapsed = time.perf_counter() - started

    assert result["evaluation_result"] == "success", "timeout must fall back to success, not hang"
    assert elapsed < 0.5, "evaluate_node must return once the timeout fires, not wait for the call"
    assert "timeout" in result["events"][0]["metadata"]["judge_note"]


def test_evaluate_node_falls_back_on_judge_error(monkeypatch):
    """Any provider/LLM exception must degrade gracefully instead of crashing the node."""

    class _BrokenLLM:
        def with_structured_output(self, _model):
            raise RuntimeError("provider is down")

    monkeypatch.setattr(nodes, "get_llm", lambda: _BrokenLLM())

    result = nodes.evaluate_node(_base_state())

    assert result["evaluation_result"] == "success"
    assert "error" in result["events"][0]["metadata"]["judge_note"]


def test_evaluate_node_cost_guard_skips_llm_once_budget_exhausted(monkeypatch):
    """Once MAX_JUDGE_CALLS_PER_THREAD is hit, no further LLM calls are made."""
    fake_structured = _FakeStructuredLLM(verdict="needs_retry")

    def _should_not_be_called():
        raise AssertionError("get_llm() must not be called once the judge budget is exhausted")

    monkeypatch.setattr(nodes, "get_llm", lambda: _should_not_be_called())
    monkeypatch.setattr(nodes, "MAX_JUDGE_CALLS_PER_THREAD", 2)

    state = _base_state(judge_call_count=2)
    result = nodes.evaluate_node(state)

    assert result["evaluation_result"] == "success"
    assert result["judge_call_count"] == 2
    assert "cost guard" in result["events"][0]["metadata"]["judge_note"]
    assert fake_structured.call_count == 0


def test_evaluate_node_error_marker_never_calls_llm(monkeypatch):
    """The deterministic ERROR-marker short-circuit must not spend an LLM call."""

    def _should_not_be_called():
        raise AssertionError("get_llm() must not be called for the deterministic ERROR case")

    monkeypatch.setattr(nodes, "get_llm", lambda: _should_not_be_called())

    state = _base_state(tool_results=["ERROR: transient tool failure on attempt 0"])
    result = nodes.evaluate_node(state)

    assert result["evaluation_result"] == "needs_retry"
    assert "heuristic" in result["events"][0]["metadata"]["judge_note"]
