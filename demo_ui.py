"""Interactive demo UI for the support-ticket agent.

Not part of the graded pipeline (run-scenarios/validate-metrics don't touch this file) —
this is a Streamlit front-end that calls the *real* compiled graph so you can type a
question and watch it flow through classify -> routing -> tool/approval/retry -> answer,
live, using real LLM calls.

Run:
    pip install -e ".[demo]"
    streamlit run demo_ui.py
"""

from __future__ import annotations

import time
import uuid

import streamlit as st
from langgraph.graph.state import CompiledStateGraph

from langgraph_agent_lab.graph import build_graph
from langgraph_agent_lab.persistence import build_checkpointer
from langgraph_agent_lab.state import Route, Scenario, initial_state

ROUTE_INFO = {
    "simple": ("🔵", "Simple", "Câu hỏi chung, trả lời thẳng không cần tool."),
    "tool": ("🟢", "Tool", "Cần tra cứu dữ liệu qua tool."),
    "missing_info": ("🟠", "Missing info", "Thiếu thông tin, agent hỏi lại."),
    "risky": ("🔴", "Risky", "Có side effect (hoàn tiền, xoá, gửi email...), phải qua duyệt."),
    "error": ("🟣", "Error", "Lỗi hệ thống, có bounded retry rồi dead-letter nếu hết lượt."),
}

NODE_INFO = {
    "intake": ("📥", "Intake"),
    "classify": ("🧭", "Classify"),
    "tool": ("🔧", "Tool"),
    "evaluate": ("🔍", "Evaluate"),
    "answer": ("💬", "Answer"),
    "clarify": ("❓", "Clarify"),
    "risky_action": ("⚠️", "Risky action"),
    "approval": ("✅", "Approval"),
    "retry": ("🔁", "Retry"),
    "dead_letter": ("☠️", "Dead letter"),
    "finalize": ("🏁", "Finalize"),
}

SAMPLE_QUESTIONS = [
    "How do I reset my password?",
    "Please lookup order status for order 12345",
    "Can you fix it?",
    "Refund this customer and send confirmation email",
    "Timeout failure while processing request",
    "Delete customer account after support verification",
]


@st.cache_resource
def get_graph() -> CompiledStateGraph:
    return build_graph(checkpointer=build_checkpointer("memory"))


st.set_page_config(page_title="Support Agent — Live Demo", page_icon="🤖", layout="centered")
st.title("🤖 Support-Ticket Agent — Live Demo")
st.caption(
    "Gõ một câu hỏi bất kỳ (kể cả câu chưa từng thấy) rồi bấm Gửi. "
    "Route được LLM phân loại thật, không hard-code theo câu mẫu."
)

with st.sidebar:
    st.subheader("Câu hỏi mẫu")
    for sample in SAMPLE_QUESTIONS:
        if st.button(sample, use_container_width=True):
            st.session_state["query"] = sample

query = st.text_input(
    "Câu hỏi của khách hàng",
    key="query",
    placeholder="vd: Refund this customer and send confirmation email",
)
submit = st.button("Gửi câu hỏi", type="primary")

if submit and query.strip():
    graph = get_graph()
    scenario = Scenario(id=f"demo-{uuid.uuid4().hex[:6]}", query=query, expected_route=Route.SIMPLE)
    state = initial_state(scenario)
    run_config = {"configurable": {"thread_id": state["thread_id"]}}

    with st.spinner("Agent đang xử lý..."):
        started_at = time.perf_counter()
        result = graph.invoke(state, config=run_config)  # type: ignore[call-overload]
        elapsed_ms = int((time.perf_counter() - started_at) * 1000)

    route = result.get("route", "unknown")
    icon, label, desc = ROUTE_INFO.get(route, ("⚪", route, ""))
    st.markdown(f"## {icon} Route: **{label}**")
    st.caption(desc)

    st.markdown("### Đường đi (mỗi bước là 1 node thật trong graph)")
    events = result.get("events", [])
    for i, event in enumerate(events, start=1):
        node = event.get("node", "?")
        node_icon, node_label = NODE_INFO.get(node, ("⬜", node))
        st.markdown(f"**{i}. {node_icon} {node_label}** — {event.get('message', '')}")

    if result.get("proposed_action"):
        st.warning(f"**Proposed action:** {result['proposed_action']}")

    if result.get("approval"):
        approval = result["approval"]
        approved = approval.get("approved")
        icon = "✅ Approved" if approved else "❌ Rejected"
        st.write(f"**Approval:** {icon} — reviewer: `{approval.get('reviewer')}`")

    if result.get("errors"):
        with st.expander(f"Retry log ({len(result['errors'])} lần)"):
            for err in result["errors"]:
                st.text(err)

    st.markdown("### Câu trả lời")
    no_answer = "(không có câu trả lời)"
    answer = result.get("final_answer") or result.get("pending_question") or no_answer
    st.success(answer)

    st.caption(f"⏱️ {elapsed_ms} ms · {len(events)} node visited · thread_id={state['thread_id']}")
elif submit:
    st.error("Nhập câu hỏi trước đã.")
