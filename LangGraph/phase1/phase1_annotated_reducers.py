# Phase 1 - Concept 2: typing.Annotated & Reducer Functions

"""
================================================================================
LEARNING MODULE: typing.Annotated & Reducer Functions in LangGraph
================================================================================

1. WHAT IS typing.Annotated?
   - Introduced in Python 3.9 (PEP 593), `Annotated[T, x]` attaches arbitrary context 
     or metadata (`x`) to a type hint (`T`).
   - Standard Python type checkers (like mypy) ignore the metadata `x` and treat 
     `Annotated[int, "metadata"]` simply as `int`.
   - Libraries like Pydantic, FastAPI, and LangGraph inspect this metadata at runtime 
     to attach special behaviors.

2. WHAT ARE REDUCER FUNCTIONS IN LANGGRAPH?
   - Default Overwrite Behavior: In LangGraph, when a node returns a dictionary update 
     (e.g., `{"count": 2}`), LangGraph's default action is to OVERWRITE the existing value 
     in state (`state["count"] = 2`).
   - Reducer Definition: A Reducer is a function with signature `(existing_value, new_value) -> combined_value`.
   - Attaching Reducers: In LangGraph state definitions, attaching a Reducer metadata function via 
     `Annotated[Type, reducer_function]` instructs LangGraph: 
     "Do NOT overwrite this field! Instead, pass the existing value and the new update into 
     `reducer_function` and store the result."

3. COMMON REDUCERS:
   - `operator.add`:
     * For `list`: Concatenates lists (`[1, 2]` + `[3]` -> `[1, 2, 3]`).
     * For `int`: Adds numbers (`5` + `1` -> `6`).
   - `langgraph.graph.message.add_messages`:
     * Appends new chat messages to history while intelligently handling message IDs 
       (overwriting if a message with the same ID already exists).
   - Custom Reducers:
     * Custom functions for deduplication, max-value tracking, or conditional merging.

4. EDGE CASES & GOTCHAS:
   - Initial State Nulls: If a reducer expects lists (e.g., `operator.add`), ensure the field 
     is initialized with an empty list `[]`. Passing `None` to `operator.add` causes a `TypeError`.
   - Returning Incorrect Types: A reducer must return data matching the field's declared type hint.

5. WHY IT MATTERS IN LANGGRAPH:
   - LangGraph agents run in cyclic loops across multiple nodes.
   - Without reducers, a retriever node updating `retrieved_chunks` would wipe out chunks 
     retrieved by previous iterations!
   - Reducers make agent memory persistent and cumulative across complex execution graphs.

6. REAL-LIFE ANALOGY:
   - Default Overwrite behavior is like erasing a chalkboard clean every time a new teacher 
     enters the room and writing only their sentence.
   - Reducer behavior (`Annotated[list, operator.add]`) is like a shared project logbook: 
     each team member appends their notes to the bottom of the logbook without erasing 
     previous entries.

7. INTERVIEW QUESTIONS & MODEL ANSWERS:
   Q1: What happens in LangGraph state if you declare a list field WITHOUT typing.Annotated?
   A1: LangGraph defaults to overwrite behavior. Any node returning a value for that key will 
       completely replace the previous list instead of appending to it.

   Q2: What is the signature of a custom reducer function in LangGraph?
   A2: A reducer function accepts two arguments: `(existing_value, new_value)` and returns 
       the merged `combined_value` of the same type.

   Q3: How does `add_messages` differ from simple list addition (`operator.add`)?
   A3: `operator.add` blindly appends all items. `add_messages` checks message IDs; if a new 
       message has an ID matching an existing message, it updates that message in-place instead 
       of duplicating it.
================================================================================
"""

import operator
from typing import TypedDict, Annotated, List, Optional
from uuid import uuid4


# =============================================================================
# PART 1: CONCEPTUAL / ISOLATED PRACTICE SNIPPET
# =============================================================================

# 1. Custom Reducer Function: Deduplicates items when appending to a list
def unique_append_reducer(existing: list[str], new_items: list[str]) -> list[str]:
    """Appends new items to existing list while maintaining uniqueness and order."""
    combined = list(existing)
    for item in new_items:
        if item not in combined:
            combined.append(item)
    return combined


# 2. Custom Reducer Function: Takes max integer value (e.g. tracking highest score)
def max_score_reducer(existing: int, new_val: int) -> int:
    return max(existing, new_val)


# 3. Defining a StateGraph TypedDict using Annotated and Reducer functions
class PracticeReducerState(TypedDict):
    # Default behavior: OVERWRITE on update
    current_step_name: str

    # Reducer: Cumulative list concatenation using standard operator.add
    accumulated_logs: Annotated[list[str], operator.add]

    # Reducer: Integer addition (counter)
    total_token_count: Annotated[int, operator.add]

    # Reducer: Custom unique list append
    unique_topics: Annotated[list[str], unique_append_reducer]

    # Reducer: Custom max tracker
    highest_confidence: Annotated[int, max_score_reducer]


def practice_reducer_simulation() -> None:
    """Simulates how LangGraph applies reducers during consecutive node updates."""
    # Initial State
    state: PracticeReducerState = {
        "current_step_name": "START",
        "accumulated_logs": ["Agent initialized."],
        "total_token_count": 150,
        "unique_topics": ["AI", "LLM"],
        "highest_confidence": 75,
    }

    print("[Initial State]", state)

    # Node 1 Update
    node1_update = {
        "current_step_name": "retriever_node",
        "accumulated_logs": ["Retrieved 5 documents."],
        "total_token_count": 300,
        "unique_topics": ["LLM", "RAG"],  # 'LLM' is duplicate
        "highest_confidence": 88,
    }

    # Simulate LangGraph state merging logic using reducers:
    state["current_step_name"] = node1_update["current_step_name"]  # Overwrite
    state["accumulated_logs"] = operator.add(state["accumulated_logs"], node1_update["accumulated_logs"])
    state["total_token_count"] = operator.add(state["total_token_count"], node1_update["total_token_count"])
    state["unique_topics"] = unique_append_reducer(state["unique_topics"], node1_update["unique_topics"])
    state["highest_confidence"] = max_score_reducer(state["highest_confidence"], node1_update["highest_confidence"])

    print("\n[State After Node 1 Update]")
    print(f"Current Step (Overwritten): {state['current_step_name']}")
    print(f"Logs (Appended): {state['accumulated_logs']}")
    print(f"Total Tokens (Summed): {state['total_token_count']}")
    print(f"Unique Topics (Deduplicated): {state['unique_topics']}")
    print(f"Highest Confidence (Max): {state['highest_confidence']}")


# =============================================================================
# PART 2: REAL PROJECT SNIPPET (ScribeGraph Agent Accumulation Pattern)
# =============================================================================

class ScribeGraphReducerState(TypedDict):
    """
    ScribeGraph State demonstrating Annotated Reducers for accumulators.
    In multi-paper analysis, multiple retrieval nodes run sequentially or 
    in parallel, accumulating chunks and execution trace logs without losing state.
    """
    query: str
    # Overwrite by default: planner replaces previous plan
    plan: Optional[str]

    # Reducer: Append newly retrieved document chunks across graph steps
    retrieved_chunks: Annotated[list[dict], operator.add]

    # Reducer: Append execution trace steps for debugging and audit trail
    trace_steps: Annotated[list[str], operator.add]

    # Reducer: Count total revisions across iteration loops
    revision_count: Annotated[int, operator.add]


def scribe_graph_reducer_demo() -> None:
    """Simulates multi-step trace and chunk accumulation in ScribeGraph."""
    sg_state: ScribeGraphReducerState = {
        "query": "Compare attention mechanisms in Transformer vs Mamba",
        "plan": None,
        "retrieved_chunks": [],
        "trace_steps": ["State initialized"],
        "revision_count": 0,
    }

    # Iteration 1: Planner updates plan and appends trace
    plan_update = {
        "plan": "Search for Transformer linear attention and Mamba selective state space models.",
        "trace_steps": ["PlannerNode: Strategy formulated."],
    }
    sg_state["plan"] = plan_update["plan"]
    sg_state["trace_steps"] = operator.add(sg_state["trace_steps"], plan_update["trace_steps"])

    # Iteration 2: Retriever updates chunks and appends trace
    retriever_update = {
        "retrieved_chunks": [{"chunk_id": 101, "text": "Selective state spaces..."}],
        "trace_steps": ["RetrieverNode: Fetched 1 chunk from ChromaDB."],
    }
    sg_state["retrieved_chunks"] = operator.add(sg_state["retrieved_chunks"], retriever_update["retrieved_chunks"])
    sg_state["trace_steps"] = operator.add(sg_state["trace_steps"], retriever_update["trace_steps"])

    print("\n[ScribeGraph Reducer Accumulation Result]")
    print(f"Plan: {sg_state['plan']}")
    print(f"Chunks Count: {len(sg_state['retrieved_chunks'])}")
    print(f"Full Audit Trace ({len(sg_state['trace_steps'])} steps):")
    for step in sg_state["trace_steps"]:
        print(f"  - {step}")


if __name__ == "__main__":
    practice_reducer_simulation()
    scribe_graph_reducer_demo()
