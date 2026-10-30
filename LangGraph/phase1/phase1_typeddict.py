# Phase 1 - Concept 1: Type Hints & TypedDict

"""
================================================================================
LEARNING MODULE: Python Type Hints & TypedDict in LangGraph
================================================================================

1. DEFINITION & PURPOSE:
   - Type Hints: Introduced in Python 3.5 (PEP 484), type hints allow developers 
     to explicitly declare the expected data type of variables, function parameters, 
     and return values (e.g., `name: str`, `count: int`).
   - TypedDict: Introduced in Python 3.8 (PEP 589), `TypedDict` is a special subclass 
     from the `typing` module used to specify type hints for key-value dictionary objects.
   - Purpose: Standard Python `dict` allows any arbitrary key and value. This leads to 
     typos (e.g., `state["usr_query"]` vs `state["user_query"]`) and runtime key errors. 
     `TypedDict` enforces a rigid structure at development time.

2. SYNTAX & VARIATIONS:
   - Class-based syntax (Standard):
       class MyState(TypedDict):
           user_id: int
           messages: list[str]
   - Functional syntax (used when keys are reserved keywords or invalid Python identifiers):
       MyState = TypedDict('MyState', {'user-id': int, 'from': str})
   - `total=False`: Allows dictionary keys to be optional during dictionary instantiation.
       class OptionalState(TypedDict, total=False):
           query: str  # All fields become optional
   - `NotRequired` / `Required` (Python 3.11+): Per-field optionality inside a TypedDict.

3. EDGE CASES & GOTCHAS:
   - Runtime Non-Enforcement: Python does NOT enforce TypedDict types at runtime by default. 
     Assigning an `int` to a `str` field won't crash Python unless validated by an external tool 
     like `mypy` or Pydantic.
   - Extra Keys: Assigning extra keys not defined in the `TypedDict` does not raise an error 
     at runtime, but IDEs and static linters will flag it as a type error.

4. WHY IT MATTERS IN LANGGRAPH:
   - In LangGraph, the central state graph (`StateGraph`) requires a state schema definition.
   - Every Node (function) in a graph receives the current state dictionary and returns 
     updates to it.
   - `TypedDict` is the primary, lightweight mechanism LangGraph uses to track state structure, 
     providing IDE autocomplete, preventing key typo bugs, and ensuring nodes interact safely.

5. REAL-LIFE ANALOGY:
   - Think of a standard `dict` like a blank sheet of paper: anyone can write any key 
     and any value anywhere on it, leading to messy, inconsistent forms.
   - A `TypedDict` is like a standardized pre-printed job application form: it specifies 
     exact named boxes (e.g., "Full Name [Text]", "Age [Number]", "Skills [List]") so 
     every applicant fills out the exact same structure without missing required fields.

6. INTERVIEW QUESTIONS & MODEL ANSWERS:
   Q1: Does TypedDict validate types at runtime when assigning values in standard Python?
   A1: No. TypedDict is purely a static type annotation tool. Python's runtime engine 
       ignores type annotations. Runtime enforcement requires validation libraries like Pydantic.

   Q2: How does TypedDict differ from Pydantic BaseModel, and why might LangGraph use both?
   A2: TypedDict operates on standard Python dictionaries without creation/validation overhead, 
       making it lightweight and fast. Pydantic BaseModel enforces types at runtime and coerces 
       data. LangGraph natively supports both TypedDict (for zero overhead) and Pydantic 
       (for strict runtime validation and OpenAPI/JSON schemas).

   Q3: How do optional keys work in TypedDict across different Python versions?
   A3: In Python 3.8+, passing `total=False` to TypedDict makes all keys optional. In Python 3.11+, 
       `NotRequired[T]` and `Required[T]` can be imported from `typing` to control key presence per field.
================================================================================
"""

from typing import TypedDict, List, Optional
from uuid import UUID, uuid4
from pydantic import BaseModel, Field


# =============================================================================
# PART 1: CONCEPTUAL / ISOLATED PRACTICE SNIPPET
# =============================================================================

# 1. Standard TypedDict definition
class BasicAgentState(TypedDict):
    user_query: str                  # Expected string
    chat_history: List[str]          # Expected list of strings
    response: Optional[str]          # String or None
    iteration_count: int             # Expected integer


# 2. Advanced TypedDict with total=False (optional keys during instantiation)
class FlexibleAgentState(TypedDict, total=False):
    session_id: str
    error_log: list[str]


def practice_typeddict_usage() -> None:
    """Demonstrates creating and manipulating a TypedDict object."""
    # Instantiating a valid dictionary conforming to BasicAgentState
    state: BasicAgentState = {
        "user_query": "What is Retrieval-Augmented Generation?",
        "chat_history": ["Hello!", "How can I help you?"],
        "response": None,
        "iteration_count": 1,
    }

    # Accessing keys with standard dictionary syntax (with IDE auto-completion)
    print(f"[Practice] Query: {state['user_query']}")
    print(f"[Practice] Iteration: {state['iteration_count']}")

    # Updating state dictionary values
    state["response"] = "RAG combines external document retrieval with LLMs."
    state["iteration_count"] += 1
    print(f"[Practice] Updated Response: {state['response']}")


# =============================================================================
# PART 2: REAL PROJECT SNIPPET (From ScribeGraph Project: quantinsight/agent/state.py)
# =============================================================================
# Below is the exact GraphState used in ScribeGraph for multi-paper academic research.
# ScribeGraph uses Pydantic BaseModel (which shares identical type-hint concepts with TypedDict).


class ScribeGraphTypedDictState(TypedDict):
    """
    TypedDict representation of the ScribeGraph Agent State.
    This schema defines the shared memory state passed between Graph Nodes:
    Planner -> Retriever -> Synthesizer -> Verifier.
    """
    query: str                                # The user's input research question
    paper_ids: list[UUID]                      # List of paper UUID targets
    plan: Optional[str]                        # High-level search strategy generated by Planner
    retrieved_chunks: list[dict]               # Document text chunks retrieved from ChromaDB
    retrieved_tables: list[dict]               # Document tables retrieved from vector store
    retrieved_equations: list[dict]            # Document LaTeX equations retrieved
    draft_answer: Optional[str]                # Initial answer draft produced by Synthesizer
    verification_notes: list[str]              # Feedback or factual error notes from Verifier
    needs_revision: bool                       # Flag triggering a revision loop if True
    revision_count: int                        # Counter enforcing max revision loop cap (e.g. max 2)
    final_answer: Optional[dict]               # Verified response output dictionary


def scribe_graph_state_demo() -> None:
    """Demonstrates how ScribeGraph initializes and updates state across node execution steps."""
    # Initializing state when user submits a query
    initial_state: ScribeGraphTypedDictState = {
        "query": "What is the primary architectural innovation in PatchTST?",
        "paper_ids": [uuid4()],
        "plan": None,
        "retrieved_chunks": [],
        "retrieved_tables": [],
        "retrieved_equations": [],
        "draft_answer": None,
        "verification_notes": [],
        "needs_revision": False,
        "revision_count": 0,
        "final_answer": None,
    }

    print("\n[ScribeGraph Project State Demo]")
    print(f"Initial Query: {initial_state['query']}")
    print(f"Paper Target IDs: {initial_state['paper_ids']}")

    # Node 1 (Planner Node) updates the plan key:
    initial_state["plan"] = "1. Retrieve patch extraction section. 2. Verify channel independence."
    print(f"Planner Node Output -> Plan: {initial_state['plan']}")


if __name__ == "__main__":
    practice_typeddict_usage()
    scribe_graph_state_demo()
