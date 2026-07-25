# AGENTS.md
## QuantInsight — Agent & Repository Conventions

This file serves two purposes:
1. **Repo conventions for AI coding assistants** (e.g., Claude Code) working on this codebase.
2. **Documentation of the LangGraph agent system itself** — the actual agents QuantInsight runs at query time.

---

## Part A — Repository Conventions (for AI coding agents working on this repo)

### Project summary
QuantInsight is a two-stage knowledge extraction and agentic retrieval framework for arXiv-style research papers. Stage 1 (ingestion) uses LlamaParse to preserve document structure; Stage 2 (retrieval) uses a stateful LangGraph agent with a self-correction loop. See `docs/01_PRD.md` and `docs/02_TRD.md` for full context before making non-trivial changes.

### Setup
```bash
uv venv
source .venv/bin/activate
uv pip install -e ".[dev]"
./scripts/pre-commit-setup.sh   # if present
```

### Running things
```bash
uv run pytest                          # run tests
uv run ruff check .                    # lint
uv run python scripts/ingest.py --arxiv-id <id>
uv run python scripts/query.py --question "..." --paper-ids <id>
uv run uvicorn quantinsight.api.main:app --reload
uv run streamlit run app/Home.py
uv run python quantinsight/eval/run_eval.py
```

### Code conventions
- **Typing is mandatory.** Every function signature, every cross-module data structure, is typed. No bare `dict`/`Any` across module boundaries — use the Pydantic models in `quantinsight/schemas/`.
- **Pydantic v2 only.** Use `model_config`, `Field`, and v2 validators — do not mix in v1-style `class Config` patterns.
- **Async by default for I/O.** LlamaParse calls, LLM calls, ChromaDB queries, and FastAPI routes should be `async def` unless there's a specific reason not to (document the reason inline if so).
- **No new UI frameworks.** UI is Streamlit only. Do not introduce React/HTML/JS/CSS files — if a Streamlit limitation is hit, document it and find a Streamlit-native workaround (e.g., `st.components.v1.html` only as a last resort, and only for KaTeX rendering support).
- **Every external call is wrapped.** LlamaParse, LLM API, ChromaDB — all get retry logic (max 2 retries) and explicit exception handling. Never let an external API failure propagate as an unhandled 500 or a silent empty result.
- **Every agent run is traced.** Any change to `quantinsight/agent/` must preserve the `AgentTraceStep` logging contract — the trace viewer in the UI depends on it, and so does the eval/debugging workflow.

### Testing expectations
- New ingestion logic → add/update a fixture paper in `tests/fixtures/` and assert expected chunk counts/types.
- New agent node → add a test in `tests/test_agent_graph.py` asserting the node's output shape, not just "it doesn't crash."
- New API route → add a test in `tests/test_api.py` using FastAPI's `TestClient`.
- Do not merge changes that drop CI-passing status.

### What NOT to do
- Do not add authentication/multi-tenancy — explicitly out of scope (see PRD §3).
- Do not add a training/fine-tuning pipeline — this project uses API-based LLMs only.
- Do not silently change the Pydantic schemas in `quantinsight/schemas/` without checking every downstream consumer (ChromaDB metadata mapping, SQLite schema, API response models, MCP tool signatures all depend on them).
- Do not commit API keys — use `.env` (gitignored), reference `.env.example` for required variables.

---

## Part B — The LangGraph Agent System (documentation of runtime agents)

QuantInsight's query-time reasoning is a single LangGraph graph with four functional roles. These are not separate deployable services — they're nodes in one stateful graph, sharing `GraphState` (see TRD §4.2).

### Agent: Planner
- **Input:** user query, list of target `paper_ids`
- **Responsibility:** decompose the query into sub-questions if needed; decide whether this is single-hop (one paper, direct lookup) or multi-hop (cross-paper comparison, or a question requiring multiple retrieval passes)
- **Output:** a `plan` string describing retrieval strategy, written into `GraphState`
- **Failure mode to guard against:** over-decomposing simple questions into unnecessary multi-step plans — keep the prompt biased toward the simplest sufficient plan

### Agent: Retriever
- **Input:** `plan`, `paper_ids`
- **Responsibility:** call the type-aware retrieval function (`search()` from Phase 2) against ChromaDB; for math-related queries, weight `equation_chunks` collection; for numeric/results questions, weight `table_chunks`
- **Output:** populates `retrieved_chunks`, `retrieved_tables`, `retrieved_equations` in `GraphState`
- **Tool bindings:** `search_papers`, `get_equation_context` (same functions exposed via MCP — the internal agent and external MCP consumers share the same underlying tool implementations, not duplicated logic)

### Agent: Synthesizer
- **Input:** retrieved chunks/tables/equations, original query
- **Responsibility:** draft an answer, always with inline citations to specific chunk IDs; must render equations as LaTeX (not paraphrase math into prose) and tables as structured data (not flattened text)
- **Output:** `draft_answer` in `GraphState`
- **Constraint:** every factual claim in the draft must be traceable to a `chunk_id` in the retrieved set — no claim without a citation

### Agent: Verifier
- **Input:** `draft_answer`, retrieved evidence
- **Responsibility:** check the draft for unsupported claims or internal contradictions against the evidence (start as an LLM self-check prompt; can be upgraded to a dedicated NLI model, following the same pattern as the DeBERTa-v3 contradiction detector used in the SEC Filing RAG project)
- **Output:** `verification_notes`, `needs_revision` boolean
- **Routing:** if `needs_revision=True`, graph routes back to Retriever (max 2 loop iterations, hard-capped to prevent infinite correction cycles); otherwise routes to final answer assembly

### Shared conventions across all four agents
- Every node appends an `AgentTraceStep` to `GraphState.trace` before returning — this is not optional, it's the contract the UI and eval tooling depend on.
- Every node is a pure function of `GraphState` in → `GraphState` (partial update) out — no hidden side effects outside what's logged in the trace.
- Every node's LLM calls use structured output (Pydantic-validated) wherever the output feeds back into `GraphState` — free-text parsing of LLM output is only acceptable for the final human-facing answer string, never for control-flow decisions like `needs_revision`.

### Adding a new agent node (future extension)
1. Define its slice of `GraphState` additions in `quantinsight/agent/state.py`.
2. Implement as `quantinsight/agent/nodes/<name>.py`, following the pure-function-plus-trace-append pattern above.
3. Wire into `quantinsight/agent/graph.py`'s graph definition, including explicit routing conditions.
4. Add a test in `tests/test_agent_graph.py`.
5. Update this file's Part B with the new agent's role — keep this document in sync with the actual graph, since it's the canonical reference for both future-you and any AI coding assistant working on the repo.
