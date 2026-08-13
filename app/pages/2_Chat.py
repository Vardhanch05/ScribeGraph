import asyncio
from uuid import UUID, uuid4
import pandas as pd
import streamlit as st
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from quantinsight.agent.graph import CHECKPOINT_DB_PATH, workflow
from quantinsight.schemas.models import AgentTraceStep, QueryResponse
from quantinsight.storage.sqlite_store import get_chunk_by_id, list_all_papers, save_agent_trace

st.set_page_config(
    page_title="Chat — ScribeGraph Agent",
    page_icon="💬",
    layout="wide",
)

st.markdown(
    """
    <style>
    .chat-header {
        font-size: 1.8rem;
        font-weight: 700;
        color: #F8FAFC;
        margin-bottom: 0.5rem;
    }
    .trace-card {
        background: rgba(15, 23, 42, 0.7);
        border: 1px solid rgba(99, 102, 241, 0.2);
        border-radius: 8px;
        padding: 0.8rem;
        margin-bottom: 0.6rem;
        font-size: 0.85rem;
    }
    .trace-node {
        font-weight: 700;
        color: #818CF8;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    .revision-badge {
        background: rgba(245, 158, 11, 0.15);
        border: 1px solid rgba(245, 158, 11, 0.4);
        color: #FBBF24;
        padding: 0.4rem 0.8rem;
        border-radius: 6px;
        font-size: 0.85rem;
        font-weight: 600;
        margin-bottom: 0.8rem;
        display: inline-block;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown('<div class="chat-header">💬 Interactive Agentic Chat</div>', unsafe_allow_html=True)
st.caption("Ask complex questions across research papers. ScribeGraph plans, retrieves, synthesizes, and self-verifies every answer.")

# Initialize session state for messages and active paper selection
if "messages" not in st.session_state:
    st.session_state["messages"] = []
if "current_trace" not in st.session_state:
    st.session_state["current_trace"] = []

# Sidebar configuration
papers = list_all_papers()
paper_map = {f"{p.title} ({p.arxiv_id or str(p.id)[:8]})": str(p.id) for p in papers}

default_selected_ids = st.session_state.get("selected_paper_ids", [])
if not default_selected_ids and paper_map:
    # Automatically default to the most recently ingested paper
    default_selected_ids = [list(paper_map.values())[-1]]

selected_paper_labels = st.sidebar.multiselect(
    "Target Papers (Leave empty for All)",
    options=list(paper_map.keys()),
    default=[k for k, v in paper_map.items() if v in default_selected_ids],
)

selected_ids = [UUID(paper_map[label]) for label in selected_paper_labels]


import re

def format_answer_with_citation_badges(answer: str, citations: list) -> tuple[str, dict[str, int]]:
    """
    Map inline UUID citations [uuid] to clean numbered badges **[1]**, **[2]**, etc.
    """
    if not citations:
        return answer, {}

    uuid_to_num = {}
    for idx, cid in enumerate(citations):
        cid_str = str(cid)
        uuid_to_num[cid_str] = idx + 1

    formatted_answer = answer
    for cid_str, num in uuid_to_num.items():
        formatted_answer = formatted_answer.replace(f"[{cid_str}]", f" **[{num}]**")

    def replace_unmapped_uuid(match):
        uid = match.group(1)
        if uid in uuid_to_num:
            return f" **[{uuid_to_num[uid]}]**"
        return match.group(0)

    formatted_answer = re.sub(r"\[([0-9a-fA-F-]{36})\]", replace_unmapped_uuid, formatted_answer)
    return formatted_answer, uuid_to_num


# Layout setup: 65% Chat, 35% Execution Trace
chat_col, trace_col = st.columns([65, 35])

with trace_col:
    st.subheader("⚡ Agent Execution Trace")
    trace_container = st.container()

    with trace_container:
        if not st.session_state["current_trace"]:
            st.info("Agent reasoning steps will stream live here during execution.")
        else:
            for step in st.session_state["current_trace"]:
                st.markdown(
                    f"""
                    <div class="trace-card">
                        <div class="trace-node">Step {step.step_index}: Node [{step.node_name}]</div>
                        <div style="color: #CBD5E1; margin-top: 4px;"><b>Input:</b> {step.input_summary}</div>
                        <div style="color: #94A3B8; margin-top: 2px;"><b>Output:</b> {step.output_summary}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

with chat_col:
    # Render chat history
    for msg in st.session_state["messages"]:
        with st.chat_message(msg["role"]):
            if msg.get("self_correction_applied"):
                st.markdown(
                    '<div class="revision-badge">⚠️ Answer revised after verification</div>',
                    unsafe_allow_html=True,
                )
            
            citations = msg.get("citations", [])
            formatted_content, _ = format_answer_with_citation_badges(msg["content"], citations)
            st.markdown(formatted_content)

            if citations:
                with st.expander("📚 View Supporting Chunk Citations"):
                    for idx, cid in enumerate(citations):
                        num = idx + 1
                        ch = get_chunk_by_id(UUID(cid) if isinstance(cid, str) else cid)
                        if ch:
                            st.caption(f"**[{num}]** **Chunk ID:** `{ch.id}` | **Page:** {ch.page_number} | **Type:** `{ch.chunk_type.value}`")
                            st.text(ch.content[:300] + "..." if len(ch.content) > 300 else ch.content)

    # Chat input
    user_input = st.chat_input("Ask a question about the papers...")

    if user_input:
        st.session_state["messages"].append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)

        with st.chat_message("assistant"):
            st.session_state["current_trace"] = []
            thread_id = uuid4()
            config = {"configurable": {"thread_id": str(thread_id)}}

            initial_state = {
                "query": user_input,
                "paper_ids": selected_ids,
                "retrieved_chunks": [],
                "retrieved_tables": [],
                "retrieved_equations": [],
                "verification_notes": [],
                "needs_revision": False,
                "revision_count": 0,
                "trace": [],
            }

            async def run_and_stream():
                sent_indices = set()
                final_answer = None

                async with AsyncSqliteSaver.from_conn_string(CHECKPOINT_DB_PATH) as checkpointer:
                    local_app = workflow.compile(checkpointer=checkpointer)
                    async for chunk in local_app.astream(initial_state, config=config, stream_mode="updates"):
                        for node_name, state_update in chunk.items():
                            if isinstance(state_update, dict):
                                trace = state_update.get("trace", [])
                                for step in trace:
                                    if step.step_index not in sent_indices:
                                        sent_indices.add(step.step_index)
                                        st.session_state["current_trace"].append(step)
                                if "final_answer" in state_update and state_update["final_answer"] is not None:
                                    final_answer = state_update["final_answer"]
                return final_answer

            with st.spinner("Agent planning and retrieving..."):
                final_response = asyncio.run(run_and_stream())

            if final_response:
                if final_response.self_correction_applied:
                    st.markdown(
                        '<div class="revision-badge">⚠️ Answer revised after verification</div>',
                        unsafe_allow_html=True,
                    )

                citations_list = [str(c) for c in final_response.citations]
                formatted_answer, _ = format_answer_with_citation_badges(final_response.answer, citations_list)
                st.markdown(formatted_answer)

                if final_response.citations:
                    with st.expander("📚 View Supporting Chunk Citations"):
                        for idx, cid in enumerate(final_response.citations):
                            num = idx + 1
                            ch = get_chunk_by_id(cid)
                            if ch:
                                st.caption(f"**[{num}]** **Chunk ID:** `{ch.id}` | **Page:** {ch.page_number} | **Type:** `{ch.chunk_type.value}`")
                                st.text(ch.content[:300] + "..." if len(ch.content) > 300 else ch.content)

                st.session_state["messages"].append(
                    {
                        "role": "assistant",
                        "content": final_response.answer,
                        "citations": citations_list,
                        "self_correction_applied": final_response.self_correction_applied,
                    }
                )
                st.rerun()
