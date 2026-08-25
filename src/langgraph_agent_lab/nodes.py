"""Node functions for the LangGraph workflow.

Each function receives AgentState and returns a partial state update dict.
Do NOT mutate input state — return new values only.

LLM REQUIREMENT:
- classify_node MUST use a real LLM call (structured output for intent classification)
- answer_node MUST use a real LLM call (grounded response generation)
- evaluate_node SHOULD use LLM-as-judge (bonus points; heuristic acceptable for base score)
"""

from __future__ import annotations

import concurrent.futures
import os
from typing import Literal, cast

from pydantic import BaseModel, Field

from .llm import get_llm
from .state import AgentState, make_event


# ─── EXAMPLE: working node (provided for reference) ──────────────────
def intake_node(state: AgentState) -> dict:
    """Normalize raw query. This node is provided as a working example."""
    query = state.get("query", "").strip()
    return {
        "query": query,
        "messages": [f"intake:{query[:40]}"],
        "events": [make_event("intake", "completed", "query normalized")],
    }


# ─── classify_node ─────────────────────────────────────────────────────


class ClassificationResult(BaseModel):
    """Structured output schema for LLM-based intent classification."""

    route: Literal["simple", "tool", "missing_info", "risky", "error"] = Field(
        description="Single best-matching route for this support ticket."
    )
    reasoning: str = Field(default="", description="One short sentence explaining the choice.")


_CLASSIFY_SYSTEM_PROMPT = """You are an intent classifier for a customer-support ticket router.
Classify the user's message into exactly ONE route. If more than one could apply, use this
priority order: risky > tool > missing_info > error > simple.

- risky: request asks to perform an action with side effects (refunds, deletions, cancellations,
  sending emails/messages, account changes). Anything with a side effect is risky even if it also
  needs a data lookup.
- tool: a read-only information lookup (order status, tracking, account details, search) with
  enough context to look it up.
- missing_info: the request is vague or missing the specific details needed to act
  (e.g. "fix it", "help me" with no specifics), and is not risky.
- error: the message describes a system failure, timeout, crash, or service outage rather than
  a normal user request.
- simple: a general question answerable directly, without tools or actions.

Return exactly one route."""


def classify_node(state: AgentState) -> dict:
    """Classify the query into a route using an LLM with structured output."""
    query = state.get("query", "")
    llm = get_llm()
    structured_llm = llm.with_structured_output(ClassificationResult)
    # with_structured_output(SomePydanticModel) always returns that model instance at
    # runtime; its return type is a broad union only because it also accepts dict schemas.
    result = cast(
        ClassificationResult,
        structured_llm.invoke(
            [
                {"role": "system", "content": _CLASSIFY_SYSTEM_PROMPT},
                {"role": "user", "content": f"Support ticket: {query}"},
            ]
        ),
    )
    risk_level = "high" if result.route == "risky" else "low"
    return {
        "route": result.route,
        "risk_level": risk_level,
        "events": [
            make_event(
                "classify",
                "completed",
                f"classified as {result.route}",
                reasoning=result.reasoning,
            )
        ],
    }


def tool_node(state: AgentState) -> dict:
    """Execute a mock tool call, simulating transient failures on the error route."""
    attempt = state.get("attempt", 0)
    route = state.get("route", "")
    query = state.get("query", "")

    if route == "error" and attempt < 2:
        result = f"ERROR: transient tool failure on attempt {attempt} for query '{query[:60]}'"
    else:
        reference_id = f"REF-{abs(hash(query)) % 100000:05d}"
        result = (
            f"SUCCESS: request handled for \"{query[:60]}\" (reference {reference_id}). "
            "Outcome: the requested action/lookup has been completed and confirmed — all "
            "necessary steps were carried out, status=confirmed, no further action is needed."
        )

    return {
        "tool_results": [result],
        "events": [
            make_event("tool", "completed", "tool executed", attempt=attempt, result=result)
        ],
    }


class EvaluationVerdict(BaseModel):
    """Structured output schema for LLM-as-judge tool-result evaluation."""

    verdict: Literal["success", "needs_retry"] = Field(
        description="'success' if the tool result usably answers the query, else 'needs_retry'."
    )
    reasoning: str = Field(default="", description="One short sentence explaining the verdict.")


_EVALUATE_SYSTEM_PROMPT = """You are a QA judge for a customer-support agent. Given the customer's
query and the tool result that was returned, decide whether the result is good enough to build a
final answer from ("success") or whether it is insufficient/unsatisfactory and the tool should be
retried ("needs_retry")."""

# Extension: LLM-as-judge is the real evaluator (not just advisory), but two guards keep it
# from threatening the bounded-retry / termination guarantees the core graph relies on:
#   - JUDGE_TIMEOUT_SECONDS bounds how long we wait for the LLM before falling back, so a slow
#     or hung API call (observed happening for real against OpenAI) can never stall the graph.
#   - MAX_JUDGE_CALLS_PER_THREAD caps LLM spend per thread; once hit, later evaluate_node calls
#     skip the API entirely and use the heuristic fallback instead.
# Both fallback paths default to "success", not "needs_retry" — an infra failure (timeout/error/
# budget) should never be indistinguishable from a real quality failure, and defaulting to
# "success" cannot create an unbounded loop (route_after_retry's max_attempts cap still applies
# either way).
JUDGE_TIMEOUT_SECONDS = 8.0
MAX_JUDGE_CALLS_PER_THREAD = 3


def _call_judge(query: str, latest_result: str) -> EvaluationVerdict:
    """Blocking call to the LLM-as-judge, bounded by JUDGE_TIMEOUT_SECONDS.

    Raises on timeout or any LLM/provider error. Deliberately does NOT use the executor as a
    context manager: `ThreadPoolExecutor.__exit__` calls shutdown(wait=True), which would block
    the caller until the slow background call finishes anyway - defeating the timeout. Instead
    we shut down without waiting, so a stuck call keeps running in the background (harmless,
    single-use executor) while evaluate_node moves on immediately.
    """
    llm = get_llm()
    structured_llm = llm.with_structured_output(EvaluationVerdict)
    messages = [
        {"role": "system", "content": _EVALUATE_SYSTEM_PROMPT},
        {"role": "user", "content": f"Customer query: {query}\n\nTool result: {latest_result}"},
    ]
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    future = executor.submit(structured_llm.invoke, messages)
    try:
        return cast(EvaluationVerdict, future.result(timeout=JUDGE_TIMEOUT_SECONDS))
    finally:
        executor.shutdown(wait=False)


def evaluate_node(state: AgentState) -> dict:
    """Evaluate the latest tool result — the retry-loop gate.

    Deterministic short-circuit: the mock tool's "ERROR" marker (simulated transient failure)
    is unambiguous by construction, so it's checked first without spending an LLM call.
    Otherwise, an LLM-as-judge is the real evaluator (structured verdict + reason), bounded by
    a timeout and a per-thread call budget — see the guards documented above.
    """
    query = state.get("query", "")
    tool_results = state.get("tool_results", [])
    latest_result = tool_results[-1] if tool_results else ""
    judge_calls = state.get("judge_call_count", 0)

    if not latest_result:
        evaluation_result = "needs_retry"
        judge_note = "heuristic: no tool result available yet"
    elif "ERROR" in latest_result:
        evaluation_result = "needs_retry"
        judge_note = "heuristic: tool result carries a simulated ERROR marker"
    elif judge_calls >= MAX_JUDGE_CALLS_PER_THREAD:
        evaluation_result = "success"
        judge_note = f"cost guard: judge call budget ({MAX_JUDGE_CALLS_PER_THREAD}) exhausted"
    else:
        judge_calls += 1
        try:
            verdict = _call_judge(query, latest_result)
            evaluation_result = verdict.verdict
            judge_note = f"llm-as-judge: {verdict.verdict} - {verdict.reasoning or 'no reason'}"
        except concurrent.futures.TimeoutError:
            evaluation_result = "success"
            judge_note = f"timeout: judge exceeded {JUDGE_TIMEOUT_SECONDS}s, fallback=success"
        except Exception as exc:  # any provider/LLM error must fall back, not crash the graph
            evaluation_result = "success"
            judge_note = f"error: judge call failed ({exc}), fallback=success"

    return {
        "evaluation_result": evaluation_result,
        "judge_call_count": judge_calls,
        "events": [
            make_event(
                "evaluate",
                "completed",
                f"evaluation={evaluation_result}",
                latest_result=latest_result,
                judge_note=judge_note,
            )
        ],
    }


_ANSWER_SYSTEM_PROMPT = """You are a customer-support assistant. Write the final reply to the
customer using ONLY the context provided below — do not invent facts, prices, dates, or ticket
numbers that are not present in the context. Be concise, polite, and directly address the
customer's request."""


def answer_node(state: AgentState) -> dict:
    """Generate a final response using an LLM, grounded in tool results / approval context."""
    llm = get_llm()
    query = state.get("query", "")
    tool_results = state.get("tool_results", [])
    approval = state.get("approval")

    context_parts: list[str] = []
    if tool_results:
        context_parts.append("Tool results:\n" + "\n".join(f"- {r}" for r in tool_results))
    if approval:
        context_parts.append(
            "Approval decision: approved={approved}, reviewer={reviewer}, comment={comment}".format(
                approved=approval.get("approved"),
                reviewer=approval.get("reviewer"),
                comment=approval.get("comment"),
            )
        )
    no_context_note = "No tool context was needed for this query."
    context = "\n\n".join(context_parts) if context_parts else no_context_note
    user_content = f"Customer query: {query}\n\nContext:\n{context}\n\nWrite the final answer."

    response = llm.invoke(
        [
            {"role": "system", "content": _ANSWER_SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ]
    )
    answer_text = response.content if hasattr(response, "content") else str(response)

    return {
        "final_answer": answer_text,
        "events": [make_event("answer", "completed", "answer generated")],
    }


def ask_clarification_node(state: AgentState) -> dict:
    """Ask for missing information instead of hallucinating."""
    query = state.get("query", "")
    question = (
        f"I need a bit more detail to help with: \"{query}\". "
        "Could you share the specific order number, account, or issue you're referring to?"
    )
    return {
        "pending_question": question,
        "final_answer": question,
        "events": [make_event("clarify", "completed", "clarification requested")],
    }


def risky_action_node(state: AgentState) -> dict:
    """Prepare a risky action for human approval."""
    query = state.get("query", "")
    proposed_action = (
        f"Proposed action requiring approval: fulfill request \"{query}\" - "
        "this has a side effect (e.g. refund, deletion, or outbound communication) "
        "and must be reviewed before execution."
    )
    return {
        "proposed_action": proposed_action,
        "events": [
            make_event(
                "risky_action",
                "completed",
                "risky action prepared",
                proposed_action=proposed_action,
            )
        ],
    }


def approval_node(state: AgentState) -> dict:
    """Human-in-the-loop approval step.

    Default: mock approval (approved=True) so tests/CI run offline.
    Extension: LANGGRAPH_INTERRUPT=true uses langgraph.types.interrupt() for real HITL.
    """
    proposed_action = state.get("proposed_action", "")

    if os.getenv("LANGGRAPH_INTERRUPT", "").lower() == "true":
        from langgraph.types import interrupt

        decision = interrupt({"proposed_action": proposed_action, "query": state.get("query", "")})
        if isinstance(decision, dict):
            approved = bool(decision.get("approved", False))
            reviewer = decision.get("reviewer", "human-reviewer")
            comment = decision.get("comment", "")
        else:
            approved = bool(decision)
            reviewer = "human-reviewer"
            comment = ""
    else:
        approved = True
        reviewer = "mock-reviewer"
        comment = "Auto-approved by mock reviewer (LANGGRAPH_INTERRUPT not enabled)."

    approval = {"approved": approved, "reviewer": reviewer, "comment": comment}
    return {
        "approval": approval,
        "events": [
            make_event("approval", "completed", "approval decision recorded", approved=approved)
        ],
    }


def retry_or_fallback_node(state: AgentState) -> dict:
    """Record a retry attempt: increment the attempt counter and log the failure."""
    attempt = state.get("attempt", 0) + 1
    route = state.get("route")
    error_message = f"Attempt {attempt} failed or was flagged for retry (route={route})."
    return {
        "attempt": attempt,
        "errors": [error_message],
        "events": [make_event("retry", "completed", "retry attempt recorded", attempt=attempt)],
    }


def dead_letter_node(state: AgentState) -> dict:
    """Handle unresolvable failures after max retries exceeded."""
    attempt = state.get("attempt", 0)
    max_attempts = state.get("max_attempts", 3)
    final_answer = (
        f"We were unable to complete your request after {attempt} attempt(s) "
        f"(limit: {max_attempts}). This has been escalated to a human agent who will "
        "follow up with you shortly. We apologize for the inconvenience."
    )
    return {
        "final_answer": final_answer,
        "events": [
            make_event(
                "dead_letter",
                "completed",
                "max retries exceeded, escalated",
                attempt=attempt,
                max_attempts=max_attempts,
            )
        ],
    }


def finalize_node(state: AgentState) -> dict:
    """Emit a final audit event. All routes must pass through here before END."""
    return {"events": [make_event("finalize", "completed", "workflow finished")]}
