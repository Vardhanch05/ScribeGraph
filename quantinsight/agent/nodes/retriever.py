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
from quantinsight.storage.hybrid_search import get_parent_prose_chunks, hybrid_search

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

    verification_notes = (
        state.verification_notes
        if hasattr(state, "verification_notes")
        else state.get("verification_notes", [])
    )

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

    # If verification notes exist (revision loop), append additional search step targeting feedback
    if verification_notes and isinstance(verification_notes, list):
        notes_str = " ".join(verification_notes)
        search_steps.append({
            "query": f"{query} {notes_str[:150]}",
            "chunk_types": [ChunkType.PROSE, ChunkType.TABLE, ChunkType.EQUATION]
        })

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
        elif (ChunkType.EQUATION in step_types or ChunkType.TABLE in step_types) and ChunkType.PROSE not in step_types:
            step_types.append(ChunkType.PROSE)

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
            results = await hybrid_search(
                query=step_query,
                paper_ids=paper_ids if paper_ids else None,
                chunk_types=step_types,
                limit=5,
            )

            # Categorize search results and resolve Parent-Child Context Linkage
            for item in results:
                if isinstance(item, PaperChunk):
                    chunk_map[item.id] = item
                elif isinstance(item, TableUnit):
                    table_map[item.id] = item
                    # Parent-Child Context Linkage: fetch surrounding parent prose chunks
                    if item.paper_id and item.page_number is not None:
                        parents = get_parent_prose_chunks(item.paper_id, item.page_number)
                        for p in parents:
                            chunk_map[p.id] = p
                elif isinstance(item, EquationUnit):
                    equation_map[item.id] = item
                    # Parent-Child Context Linkage: fetch surrounding parent prose chunks
                    if item.paper_id and item.page_number is not None:
                        parents = get_parent_prose_chunks(item.paper_id, item.page_number)
                        for p in parents:
                            chunk_map[p.id] = p

        except Exception as e:
            logger.error(f"Hybrid search failed for step {step}: {e}")

    # Inject foundational Paper Metadata and CitedSummary for target papers
    from uuid import uuid5, NAMESPACE_DNS
    from quantinsight.storage.sqlite_store import get_paper_by_id, get_paper_summary

    if paper_ids:
        for pid in paper_ids:
            paper = get_paper_by_id(pid)
            summary = get_paper_summary(pid)
            if paper:
                meta_text = (
                    f"Document Metadata:\n"
                    f"Paper Title: {paper.title}\n"
                    f"Authors: {', '.join(paper.authors) if paper.authors else 'Unknown'}\n"
                    f"arXiv ID: {paper.arxiv_id or 'N/A'}\n"
                    f"Total Page Count: {paper.page_count}\n"
                )
                if summary and summary.summary:
                    meta_text += f"\nSummary of Paper:\n{summary.summary}\n"
                if summary and summary.key_claims:
                    meta_text += f"\nKey Claims:\n" + "\n".join(f"- {c}" for c in summary.key_claims)

                meta_chunk_id = uuid5(NAMESPACE_DNS, f"meta_{pid}")
                meta_chunk = PaperChunk(
                    id=meta_chunk_id,
                    paper_id=pid,
                    chunk_type=ChunkType.PROSE,
                    content=meta_text,
                    page_number=1,
                    section_title="Document Title & Cited Summary Metadata",
                    order_index=-1,
                )
                chunk_map[meta_chunk_id] = meta_chunk

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
