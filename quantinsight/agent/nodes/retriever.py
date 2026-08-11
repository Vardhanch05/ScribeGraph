import json
import logging
from datetime import datetime, timezone
from typing import Any

from quantinsight.agent.state import GraphState
from quantinsight.schemas.models import (
    AgentTraceStep,
    ChunkType,
    EquationUnit,
    PaperChunk,
    TableUnit,
)
from quantinsight.storage.chroma_store import search

logger = logging.getLogger(__name__)


async def retriever_node(state: GraphState | dict[str, Any]) -> dict[str, Any]:
    """
    Retriever node: Executes type-aware search queries based on the plan,
    populates retrieved results, and logs trace step.
    """
    # Extract state fields robustly (handles both Pydantic model and dict)
    query = state.query if hasattr(state, "query") else state.get("query", "")
    paper_ids = (
        state.paper_ids
        if hasattr(state, "paper_ids")
        else state.get("paper_ids", [])
    )
    plan_str = state.plan if hasattr(state, "plan") else state.get("plan")
    trace = state.trace if hasattr(state, "trace") else state.get("trace", [])

    # Previous retrieved elements (if this is a loop/revision step, we might want to keep or replace them)
    # The requirement is to "populate retrieved_chunks, retrieved_tables, retrieved_equations in state"
    # To handle the verification loop (Task 29, 30), it is best to aggregate or update them.
    # Let's accumulate or start fresh depending on whether this is a loop.
    # In LangGraph, when looping, we can either append or replace. Let's merge and deduplicate
    # to make sure we don't lose previous context but also get new results.
    existing_chunks = (
        state.retrieved_chunks
        if hasattr(state, "retrieved_chunks")
        else state.get("retrieved_chunks", [])
    )
    existing_tables = (
        state.retrieved_tables
        if hasattr(state, "retrieved_tables")
        else state.get("retrieved_tables", [])
    )
    existing_equations = (
        state.retrieved_equations
        if hasattr(state, "retrieved_equations")
        else state.get("retrieved_equations", [])
    )

    step_index = len(trace)

    # 1. Parse plan to extract search queries
    search_steps = []
    if plan_str:
        try:
            plan_data = json.loads(plan_str)
            search_steps = plan_data.get("search_queries", [])
        except Exception as e:
            logger.warning(f"Failed to parse plan JSON: {e}. Falling back to default query.")

    # Fallback to default if no steps extracted
    if not search_steps:
        # If no plan search steps, query all chunk types with the original user query
        search_steps = [
            {
                "query": query,
                "chunk_types": [
                    ChunkType.PROSE,
                    ChunkType.TABLE,
                    ChunkType.EQUATION,
                ],
            }
        ]

    # Map chunk_type strings to ChunkType enum
    type_mapping = {
        "prose": ChunkType.PROSE,
        "table": ChunkType.TABLE,
        "equation": ChunkType.EQUATION,
        "figure_caption": ChunkType.FIGURE_CAPTION,
    }

    tool_calls = []
    chunk_map = {c.id: c for c in existing_chunks}
    table_map = {t.id: t for t in existing_tables}
    equation_map = {eq.id: eq for eq in existing_equations}

    # 2. Run searches
    for idx, step in enumerate(search_steps):
        step_query = step.get("query", query)
        step_types_str = step.get("chunk_types", [])

        # Convert string list to ChunkType list
        step_types = []
        for t_str in step_types_str:
            if isinstance(t_str, str):
                t_lower = t_str.lower()
                if t_lower in type_mapping:
                    step_types.append(type_mapping[t_lower])
            elif isinstance(t_str, ChunkType):
                step_types.append(t_str)

        # Default to all types if empty
        if not step_types:
            step_types = [ChunkType.PROSE, ChunkType.TABLE, ChunkType.EQUATION]

        # Record tool call metadata for CP-8 / NFR-4
        tool_call_id = f"search_{idx}_{step_index}"
        tool_calls.append(
            {
                "id": tool_call_id,
                "type": "function",
                "function": {
                    "name": "search",
                    "arguments": json.dumps(
                        {
                            "query": step_query,
                            "paper_ids": [str(pid) for pid in paper_ids],
                            "chunk_types": [t.value for t in step_types],
                        }
                    ),
                },
            }
        )

        try:
            results = await search(
                query=step_query,
                paper_ids=paper_ids if paper_ids else None,
                chunk_types=step_types,
                limit=5,
            )


            # Categorize search results
            for item in results:
                if isinstance(item, PaperChunk):
                    chunk_map[item.id] = item
                elif isinstance(item, TableUnit):
                    table_map[item.id] = item
                elif isinstance(item, EquationUnit):
                    equation_map[item.id] = item
        except Exception as e:
            logger.error(f"Search failed for step {step}: {e}")

    retrieved_chunks = list(chunk_map.values())
    retrieved_tables = list(table_map.values())
    retrieved_equations = list(equation_map.values())

    # 3. Create trace step
    input_sum = f"Plan: {plan_str}"
    output_sum = (
        f"Retrieved {len(retrieved_chunks)} chunks, "
        f"{len(retrieved_tables)} tables, "
        f"{len(retrieved_equations)} equations."
    )

    trace_step = AgentTraceStep(
        step_index=step_index,
        node_name="Retriever",
        input_summary=input_sum,
        output_summary=output_sum,
        tool_calls=tool_calls,
        timestamp=datetime.now(timezone.utc),
    )

    new_trace = list(trace) + [trace_step]

    return {
        "retrieved_chunks": retrieved_chunks,
        "retrieved_tables": retrieved_tables,
        "retrieved_equations": retrieved_equations,
        "trace": new_trace,
    }
