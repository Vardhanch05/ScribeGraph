import json
import logging
from datetime import datetime, timezone
from typing import Any

from quantinsight.agent.llm import call_groq, extract_json, is_mock_enabled
from quantinsight.agent.state import GraphState
from quantinsight.schemas.models import AgentTraceStep

logger = logging.getLogger(__name__)


async def planner_node(state: GraphState | dict[str, Any]) -> dict[str, Any]:
    """
    Planner node: Decomposes the user query and decides between single-hop
    and multi-hop retrieval.
    """
    # Extract state fields robustly (handles both Pydantic model and dict)
    query = state.query if hasattr(state, "query") else state.get("query", "")
    paper_ids = (
        state.paper_ids
        if hasattr(state, "paper_ids")
        else state.get("paper_ids", [])
    )
    trace = state.trace if hasattr(state, "trace") else state.get("trace", [])

    step_index = len(trace)

    system_prompt = (
        "You are the Planner node in an agentic RAG system for research papers.\n"
        "Your task is to analyze the user's query and decide:\n"
        "1. Is this a multi-hop or multi-paper query that requires synthesizing multiple pieces of information?\n"
        "2. A sequence of search query steps (each with a specific text query and a list of chunk types: 'prose', 'table', 'equation').\n"
        "3. A detailed plan string describing the retrieval strategy.\n\n"
        "You MUST respond ONLY with a JSON object matching this schema:\n"
        "{\n"
        '  "is_multihop": boolean,\n'
        '  "plan": "detailed plan string description",\n'
        '  "search_queries": [\n'
        "    {\n"
        '      "query": "query string to search",\n'
        '      "chunk_types": ["prose", "table", "equation"]\n'
        "    }\n"
        "  ]\n"
        "}\n\n"
        "Guidelines for chunk_types:\n"
        "- Use 'equation' if the query refers to mathematical formulas, proofs, or derivations.\n"
        "- Use 'table' if the query asks for numerical results, model comparison, or performance metrics.\n"
        "- Use 'prose' for general questions, high-level ideas, and descriptive text."
    )

    user_prompt = (
        f"User Query: {query}\n" f"Target Paper IDs: {list(map(str, paper_ids))}"
    )

    if is_mock_enabled():
        logger.info("Planner: using mock planner response.")
        # Detect if it's a math/equation query mock-style
        chunk_types = ["prose"]
        q_lower = query.lower()
        if "equation" in q_lower or "formula" in q_lower or "latex" in q_lower or "$" in q_lower:
            chunk_types = ["equation"]
        elif "table" in q_lower or "results" in q_lower or "accuracy" in q_lower or "score" in q_lower:
            chunk_types = ["table"]

        plan_data = {
            "is_multihop": len(paper_ids) > 1 or "compare" in q_lower,
            "plan": f"Mock plan: Retrieve relevant {chunk_types[0]} content for the query.",
            "search_queries": [{"query": query, "chunk_types": chunk_types}],
        }
    else:
        try:
            raw_response = await call_groq(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                response_json=True,
            )
            plan_data = extract_json(raw_response)
        except Exception as e:
            logger.error(f"Planner failed to call LLM: {e}. Falling back to default plan.")
            plan_data = {
                "is_multihop": len(paper_ids) > 1,
                "plan": f"Fallback plan: Direct retrieval for '{query}'.",
                "search_queries": [{"query": query, "chunk_types": ["prose", "equation", "table"]}],
            }

    # Format the plan data as a JSON string to store in the 'plan' state field
    plan_str = json.dumps(plan_data)

    # Prepare trace step
    trace_step = AgentTraceStep(
        step_index=step_index,
        node_name="Planner",
        input_summary=f"Query: {query}, Paper IDs: {list(map(str, paper_ids))}",
        output_summary=f"Plan: {plan_data.get('plan')}, Is Multihop: {plan_data.get('is_multihop')}",
        tool_calls=[],
        timestamp=datetime.now(timezone.utc),
    )

    new_trace = list(trace) + [trace_step]

    return {
        "plan": plan_str,
        "trace": new_trace,
    }
