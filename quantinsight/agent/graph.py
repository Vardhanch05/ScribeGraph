import os
from typing import Any
from uuid import UUID, uuid4

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from quantinsight.agent.nodes.planner import planner_node
from quantinsight.agent.nodes.retriever import retriever_node
from quantinsight.agent.nodes.synthesizer import synthesizer_node
from quantinsight.agent.nodes.verifier import verifier_node
from quantinsight.agent.state import GraphState
from quantinsight.schemas.models import QueryResponse
from quantinsight.storage.sqlite_store import save_agent_trace

WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
CHECKPOINT_DB_PATH = os.path.join(WORKSPACE_ROOT, "data", "checkpoints.db")

# Create data directory if it doesn't exist
os.makedirs(os.path.dirname(CHECKPOINT_DB_PATH), exist_ok=True)


def route_after_synthesizer(state: GraphState | dict[str, Any]) -> str:
    """
    Decides the next node after Synthesizer runs.
    Routes to verifier if final_answer is not yet compiled, otherwise END.
    """
    final_answer = (
        state.final_answer
        if hasattr(state, "final_answer")
        else state.get("final_answer")
    )
    if final_answer is not None:
        return END
    return "verifier"


def route_after_verifier(state: GraphState | dict[str, Any]) -> str:
    """
    Decides the next node after Verifier runs.
    Routes to retriever if revision is required and loop cap is not exceeded,
    otherwise synthesizer (for final mode compilation).
    """
    needs_revision = (
        state.needs_revision
        if hasattr(state, "needs_revision")
        else state.get("needs_revision", False)
    )
    revision_count = (
        state.revision_count
        if hasattr(state, "revision_count")
        else state.get("revision_count", 0)
    )

    if needs_revision and revision_count < 2:
        return "retriever"
    return "synthesizer"


# 1. Build the StateGraph
workflow = StateGraph(GraphState)

# 2. Register Nodes
workflow.add_node("planner", planner_node)
workflow.add_node("retriever", retriever_node)
workflow.add_node("synthesizer", synthesizer_node)
workflow.add_node("verifier", verifier_node)

# 3. Configure Edges & Routing
workflow.add_edge(START, "planner")
workflow.add_edge("planner", "retriever")
workflow.add_edge("retriever", "synthesizer")

# Synthesizer is followed conditionally:
# either goes to verifier (draft mode) or END (final mode)
workflow.add_conditional_edges(
    "synthesizer",
    route_after_synthesizer,
    {
        "verifier": "verifier",
        END: END,
    },
)

# Verifier is followed conditionally:
# either goes to retriever (for loop iteration) or synthesizer (to compile final answer)
workflow.add_conditional_edges(
    "verifier",
    route_after_verifier,
    {
        "retriever": "retriever",
        "synthesizer": "synthesizer",
    },
)

# 4. Compile default app with MemorySaver (useful for in-memory streaming/testing)
memory_checkpointer = MemorySaver()
app = workflow.compile(checkpointer=memory_checkpointer)


async def run_agent(
    query: str, paper_ids: list[UUID], thread_id: UUID | None = None
) -> QueryResponse:
    """
    Asynchronously run the LangGraph agent for a query over a set of papers,
    persisting checkpoints and trace steps, and returning the QueryResponse.
    """
    if thread_id is None:
        thread_id = uuid4()

    config = {"configurable": {"thread_id": str(thread_id)}}

    initial_state = {
        "query": query,
        "paper_ids": paper_ids,
        "retrieved_chunks": [],
        "retrieved_tables": [],
        "retrieved_equations": [],
        "verification_notes": [],
        "needs_revision": False,
        "revision_count": 0,
        "trace": [],
    }

    # Setup AsyncSqliteSaver checkpointer for production runs
    from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

    async with AsyncSqliteSaver.from_conn_string(CHECKPOINT_DB_PATH) as checkpointer:
        local_app = workflow.compile(checkpointer=checkpointer)
        result = await local_app.ainvoke(initial_state, config=config)

    final_answer = result.get("final_answer")
    if not final_answer:
        raise RuntimeError("Agent execution did not produce a final QueryResponse.")

    # Persist agent trace steps to SQLite
    save_agent_trace(thread_id, final_answer.trace)

    return final_answer
