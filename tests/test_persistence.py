"""Persistence / crash-resume evidence tests.

Verifies the SQLite checkpointer extension: state history is recorded per thread_id,
and a *new* checkpointer instance pointed at the same database file (simulating a
fresh process after a crash/restart) can still read the persisted state.

Note: requires a configured LLM (OPENAI_API_KEY or ANTHROPIC_API_KEY) because
classify_node and answer_node use real LLM calls.
"""

import importlib.util
import os

import pytest

pytestmark = [
    pytest.mark.skipif(
        importlib.util.find_spec("langgraph") is None,
        reason="langgraph not installed",
    ),
    pytest.mark.skipif(
        importlib.util.find_spec("langgraph.checkpoint.sqlite") is None,
        reason="langgraph-checkpoint-sqlite not installed",
    ),
    pytest.mark.skipif(
        not os.getenv("GEMINI_API_KEY")
        and not os.getenv("OPENAI_API_KEY")
        and not os.getenv("ANTHROPIC_API_KEY"),
        reason="No LLM API key configured (set GEMINI_API_KEY, OPENAI_API_KEY, or ANTHROPIC_API_KEY)",
    ),
]

from langgraph_agent_lab.graph import build_graph
from langgraph_agent_lab.persistence import build_checkpointer
from langgraph_agent_lab.state import Route, Scenario, initial_state


def test_sqlite_checkpointer_records_state_history(tmp_path):
    """A run through the SQLite checkpointer must leave more than one checkpoint."""
    db_path = str(tmp_path / "checkpoints.sqlite")
    checkpointer = build_checkpointer("sqlite", db_path)
    graph = build_graph(checkpointer=checkpointer)

    scenario = Scenario(
        id="persist-history", query="How do I reset my password?", expected_route=Route.SIMPLE
    )
    state = initial_state(scenario)
    run_config = {"configurable": {"thread_id": state["thread_id"]}}

    result = graph.invoke(state, config=run_config)
    assert result.get("final_answer")

    history = list(graph.get_state_history(run_config))
    assert len(history) > 1, "expected multiple checkpoints across the graph run"


def test_sqlite_checkpointer_survives_process_restart(tmp_path):
    """A brand-new checkpointer/graph instance pointed at the same file must see the
    persisted state — this is the crash-resume evidence: no in-memory state is required."""
    db_path = str(tmp_path / "checkpoints.sqlite")
    thread_id = "thread-persist-resume"
    run_config = {"configurable": {"thread_id": thread_id}}

    first_checkpointer = build_checkpointer("sqlite", db_path)
    first_graph = build_graph(checkpointer=first_checkpointer)
    scenario = Scenario(
        id="persist-resume", query="How do I reset my password?", expected_route=Route.SIMPLE
    )
    state = initial_state(scenario)
    state["thread_id"] = thread_id
    first_graph.invoke(state, config=run_config)

    # Simulate a fresh process: a new checkpointer/graph instance, same database file.
    second_checkpointer = build_checkpointer("sqlite", db_path)
    second_graph = build_graph(checkpointer=second_checkpointer)
    recovered = second_graph.get_state(run_config)

    assert recovered.values.get("final_answer"), "state should be recoverable from disk"
    assert recovered.values.get("thread_id") == thread_id
