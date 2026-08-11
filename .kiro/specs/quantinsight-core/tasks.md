# Tasks — QuantInsight Core

## Phase 0 — Project Setup

- [ ] 1. Initialize repo, `uv venv`, and `pyproject.toml` with dependency groups (core, dev, eval)
  - Set up `uv venv` and activate virtual environment
  - Create `pyproject.toml` with `[project]`, `[project.optional-dependencies]` groups for core, dev, eval
  - Run `uv pip install -e .` and confirm it resolves cleanly
  - Relevant requirements: NFR-5

- [ ] 2. Set up pre-commit config and GitHub Actions CI
  - Create `.pre-commit-config.yaml` with ruff, ruff-format, and pyright/mypy hooks
  - Create `.github/workflows/ci.yml` running lint + pytest on push to `main`
  - Confirm `uv run pytest` runs with zero tests and exits green
  - Relevant requirements: NFR-5

- [ ] 3. Create `.env.example` and repo scaffolding
  - Add `.env.example` documenting all required keys (LLM provider, LlamaParse)
  - Create empty `__init__.py` files and directory stubs matching the structure in `structure.md`
  - Add `AGENTS.md` at repo root
  - Relevant requirements: NFR-5

## Phase 1 — Data Contracts & Ingestion Core

- [ ] 4. Implement `SourcePaper` and `PaperChunk` schemas
  - Define `ChunkType` enum and `SourcePaper` model in `quantinsight/schemas/`
  - Define `PaperChunk` model with all fields from design.md
  - All fields typed; use Pydantic v2 `Field` and `model_config`
  - Relevant requirements: FR-3, NFR-2

- [ ] 5. Implement `TableUnit` and `EquationUnit` schemas
  - Define `TableUnit` with `headers`, `rows`, `caption`, `page_number`, `chunk_id`
  - Define `EquationUnit` with `latex`, `surrounding_context`, `equation_label`, `page_number`, `chunk_id`
  - Relevant requirements: FR-3, NFR-2, CP-3

- [ ] 6. Implement `Citation`, `CitedSummary`, `AgentTraceStep`, and `QueryResponse` schemas
  - Define remaining models from design.md data models section
  - Ensure `CitedSummary.supporting_chunk_ids` is `list[UUID]`
  - Ensure `QueryResponse.citations` is `list[UUID]`
  - Relevant requirements: FR-4, FR-10, NFR-2, CP-4, CP-6, CP-8

- [ ] 7. Implement LlamaParse client wrapper (`ingestion/parser.py`)
  - Async function accepting arXiv ID or PDF bytes
  - For arXiv ID: fetch PDF from `https://arxiv.org/pdf/{id}`
  - Call LlamaParse API, return raw Markdown string
  - Wrap with retry decorator (max 2 retries) and explicit exception handling
  - Relevant requirements: FR-1, FR-2, NFR-3

- [ ] 8. Add `asyncio.Semaphore`-based rate limiter to parser
  - Wrap LlamaParse calls with `asyncio.Semaphore(20)` + short sleep
  - Ensures batch ingestion stays under 20 req/min free-tier cap
  - Relevant requirements: NFR-6

- [ ] 9. Implement artifact persistence in parser
  - After every LlamaParse call, persist raw Markdown to `/artifacts/{paper_id}/raw.md`
  - Check for existing artifact before calling LlamaParse (48h cache avoidance)
  - Relevant requirements: NFR-7, CP-1

- [ ] 10. Implement segmentation logic (`ingestion/segmenter.py`)
  - Parse raw Markdown into prose blocks, LaTeX delimiters, table blocks
  - Produce typed `PaperChunk`, `TableUnit`, `EquationUnit` objects
  - Assign `order_index` preserving reading order; record `page_number` from LlamaParse metadata
  - Relevant requirements: FR-3, CP-1, CP-3

- [ ] 11. Implement low-confidence extraction flagging in segmenter
  - Flag extractions where table row/column parsing is uncertain
  - Surface warnings via return value (do not silently drop — propagate to API/UI)
  - Relevant requirements: FR-3, NFR-3

- [ ] 12. Implement `CitedSummary` generation
  - Single async LLM call over full paper content
  - Structured-output prompt requiring every key claim to reference at least one `chunk_id`
  - Validate output against `CitedSummary` schema
  - Relevant requirements: FR-4, CP-4

- [ ] 13. Implement idempotent re-ingestion logic
  - On re-ingest of same `arxiv_id`: look up existing `SourcePaper`, update in place
  - Upsert chunks by stable ID; never insert duplicates
  - Relevant requirements: FR-5, CP-5

- [ ] 14. Write ingestion unit tests
  - Add fixture paper to `tests/fixtures/`
  - Assert expected chunk counts and types for the fixture paper
  - Assert at least one `EquationUnit` extracted with valid `latex` field
  - Assert at least one `TableUnit` where `len(row) == len(headers)` for all rows (CP-3)
  - Relevant requirements: FR-2, FR-3, CP-3

- [ ] 15. Implement `scripts/ingest.py` CLI and validate against real papers
  - CLI accepting `--arxiv-id` or `--pdf` flags
  - Run end-to-end against 2–3 real arXiv papers; inspect output objects
  - Document any LlamaParse fidelity issues found in `HANDOFF.md` decisions log
  - Relevant requirements: FR-1, FR-2, FR-3

## Phase 2 — Storage & Retrieval

- [x] 16. Set up ChromaDB collections
  - Create `prose_chunks`, `table_chunks`, `equation_chunks` collections in `storage/chroma_store.py`
  - Async read/write functions; wrap with retry (max 2) + exception handling
  - Relevant requirements: FR-8, NFR-3

- [x] 17. Set up SQLite schema (`storage/sqlite_store.py`)
  - Tables: `source_papers`, `paper_chunks`, `table_units`, `equation_units`, `citations`, `cited_summaries`
  - Foreign keys enforced; separate DB file for LangGraph checkpoints
  - Relevant requirements: NFR-2, CP-4, CP-5

- [ ] 18. Implement embedding generation on ingest
  - Generate embeddings for each chunk type on ingest
  - Store embedding ID back into `PaperChunk.embedding_id`
  - Relevant requirements: FR-8

- [ ] 19. Implement type-aware `search()` function
  - `search(query, paper_ids, chunk_types) -> list[PaperChunk | TableUnit | EquationUnit]`
  - Routes to correct ChromaDB collection based on `chunk_types`
  - Fully typed return; no bare dicts
  - Relevant requirements: FR-8, NFR-2

- [ ] 20. Implement multi-paper query support in `search()`
  - Accept `paper_ids: list[UUID]` and filter results to those papers
  - Handle empty `paper_ids` as "search all ingested papers"
  - Relevant requirements: FR-6, FR-8

- [ ] 21. Write retrieval unit tests
  - Ingest a known fixture paper, run a known query, assert expected chunk is in results
  - Test type-aware routing: equation query surfaces `EquationUnit`, not prose
  - Relevant requirements: FR-8, CP-6

- [ ] 22. Ingest dev corpus (3–4 real papers)
  - Ingest 3–4 arXiv papers covering diverse equation/table density
  - Confirm all chunk types are represented in storage
  - Relevant requirements: FR-1, FR-2, FR-3

- [ ] 23. Manual relevance spot-check script
  - Small script running 5–10 queries against the dev corpus and printing results
  - Used to manually verify retrieval quality before building the agent
  - Relevant requirements: FR-8

- [ ] 24. Retrieval tuning fixes
  - Address any relevance issues found in task 23
  - Document tuning decisions in `HANDOFF.md`
  - Relevant requirements: FR-8

## Phase 3 — LangGraph Agent Loop

- [ ] 25. Define `GraphState` schema (`agent/state.py`)
  - Implement `GraphState` as Pydantic model with all fields from design.md
  - Include `revision_count: int = 0` for CP-7 enforcement
  - Relevant requirements: NFR-2, CP-7, CP-8

- [ ] 26. Implement Planner node (`agent/nodes/planner.py`)
  - Decompose query; decide single-hop vs multi-hop
  - Write `plan` string to `GraphState`
  - Append `AgentTraceStep` before returning (CP-8)
  - Use structured LLM output for plan; no free-text control-flow parsing
  - Relevant requirements: FR-7, NFR-4, CP-8

- [ ] 27. Implement Retriever node (`agent/nodes/retriever.py`)
  - Call `search()` from Phase 2 with type-aware parameters from `plan`
  - Populate `retrieved_chunks`, `retrieved_tables`, `retrieved_equations` in state
  - Append `AgentTraceStep` before returning
  - Relevant requirements: FR-8, NFR-4, CP-8

- [ ] 28. Implement Synthesizer node — draft mode (`agent/nodes/synthesizer.py`)
  - Generate draft answer with inline citations to specific chunk IDs
  - Equations rendered as LaTeX, tables as structured data — no flattening
  - Append `AgentTraceStep` before returning
  - Relevant requirements: FR-9, FR-10, NFR-4, CP-8

- [ ] 29. Implement Verifier node (`agent/nodes/verifier.py`)
  - LLM self-check of draft answer against retrieved evidence
  - Set `needs_revision: bool` and `verification_notes: list[str]` in state
  - Use structured output for `needs_revision` — no free-text boolean parsing
  - Append `AgentTraceStep` before returning
  - Relevant requirements: FR-9, NFR-4, CP-8

- [ ] 30. Wire conditional routing in graph (`agent/graph.py`)
  - Connect nodes: START → Planner → Retriever → Synthesizer → Verifier
  - Router: `needs_revision=True` AND `revision_count < 2` → Retriever; else → Synthesizer(final)
  - Increment `revision_count` on each revision loop
  - Relevant requirements: FR-9, CP-7

- [ ] 31. Implement max-iteration guard and no-evidence fallback
  - Hard cap: router blocks revision once `revision_count >= 2` (CP-7)
  - No-evidence path: Synthesizer emits structured "no supporting evidence found" response when retrieved sets are empty
  - Relevant requirements: FR-9, CP-7

- [ ] 32. Add LangGraph SQLite checkpointing
  - Configure SQLite-backed checkpointer (separate DB from main metadata store)
  - Confirm thread state can be inspected after a run completes
  - Relevant requirements: NFR-4

- [ ] 33. Implement `AgentTraceStep` persistence contract
  - After each run, persist full `trace` list to SQLite alongside checkpoint
  - Trace must survive process restart — not just in-memory
  - Relevant requirements: NFR-4, CP-8

- [ ] 34. Implement "no evidence found" structured response path
  - Synthesizer returns `QueryResponse` with empty `citations` and explicit `confidence_note`
  - Never hallucinate an answer when retrieved sets are empty
  - Relevant requirements: FR-10, NFR-3

- [ ] 35. Enforce structured LLM output across all nodes
  - All LLM calls feeding back into `GraphState` use Pydantic-validated structured output
  - Free-text parsing of LLM output only acceptable for final human-facing `answer` string
  - Relevant requirements: NFR-2

- [ ] 36. Write agent graph tests (5 known questions)
  - `tests/test_agent_graph.py`: run graph against 5 questions with known expected citations
  - Assert `final_answer.citations` contains expected chunk IDs
  - Assert `trace` length equals number of node executions (CP-8)
  - Relevant requirements: FR-7, FR-9, FR-10, CP-7, CP-8

- [ ] 37. Write revision-loop test case
  - Craft a question that forces `needs_revision=True` on first pass
  - Assert `self_correction_applied=True` in `QueryResponse`
  - Assert `revision_count` never exceeds 2 (CP-7)
  - Relevant requirements: FR-9, CP-7

- [ ] 38. Implement `scripts/query.py` CLI and validate end-to-end
  - CLI accepting `--question` and `--paper-ids` flags
  - Run full graph; print `QueryResponse` with trace steps
  - Validate at least one example where Verifier triggers a real revision
  - Relevant requirements: FR-6, FR-7, FR-9, FR-10

- [ ] 39. Prompt tuning and failure-mode documentation
  - Test against edge cases: empty retrieval, ambiguous queries, multi-paper comparisons
  - Document failures and tuning decisions in `HANDOFF.md`
  - Relevant requirements: FR-7, FR-9

## Phase 4 — API Layer

- [ ] 40. Implement FastAPI app skeleton (`api/main.py`)
  - App factory with middleware: structured error handling (no raw stack traces to client)
  - All request/response models reference schemas from `quantinsight/schemas/`
  - Relevant requirements: FR-13, NFR-2, NFR-3

- [x] 41. Implement `/ingest` and `/ingest/{paper_id}/status` endpoints
  - `POST /ingest`: accepts `arxiv_id` or `UploadFile`; triggers ingestion pipeline; returns `{paper_id: UUID}`
  - `GET /ingest/{paper_id}/status`: returns status string + `SourcePaper` if complete
  - Relevant requirements: FR-1, FR-13

- [x] 42. Implement `/papers` and `/papers/{paper_id}` endpoints
  - `GET /papers`: list all `SourcePaper` records
  - `GET /papers/{paper_id}`: return `SourcePaper` + `CitedSummary`
  - Relevant requirements: FR-13

- [x] 43. Implement `/query` endpoint
  - `POST /query`: accepts `{query: str, paper_ids: list[UUID]}`; runs agent graph; returns `QueryResponse`
  - Relevant requirements: FR-6, FR-13

- [x] 44. Implement `/query/stream` SSE endpoint and error middleware
  - `POST /query/stream`: SSE stream of `AgentTraceStep` objects — for external clients only
  - Finalize error handling middleware: all 4xx/5xx responses are structured Pydantic models
  - Relevant requirements: FR-13, NFR-3

- [x] 45. Write API tests (`tests/test_api.py`)
  - Use FastAPI `TestClient`; test all endpoints for happy path + error cases
  - Assert response bodies validate against expected Pydantic schemas
  - Relevant requirements: FR-13, NFR-2

## Phase 5 — MCP Server

- [x] 46. Implement `search_papers` and `get_paper_summary` MCP tools
  - FastMCP server in `mcp_server/server.py`
  - `search_papers(query, paper_ids)` reuses `storage/chroma_store.py` search — no duplicated logic
  - `get_paper_summary(paper_id)` reads from SQLite `cited_summaries` table
  - Relevant requirements: FR-14

- [x] 47. Implement `get_equation_context` and `ask_quantinsight` MCP tools
  - `get_equation_context(paper_id, equation_label)` looks up `EquationUnit` by label
  - `ask_quantinsight(query, paper_ids)` delegates to full agent graph; returns `QueryResponse`
  - Relevant requirements: FR-14

- [x] 48. Validate MCP server with external client and document tool schemas
  - Test all four tools with an MCP-compatible client (e.g., Claude Desktop)
  - Confirm tools are discoverable and return valid typed responses
  - Add MCP usage documentation to README
  - Relevant requirements: FR-14

## Phase 6 — Streamlit UI

- [ ] 49. Implement Home / Paper Library page (`app/Home.py`)
  - Table of ingested papers: title, authors, arXiv ID, ingestion date, chunk counts
  - "Chat about this paper" button per row; empty-state CTA linking to Ingest page
  - Relevant requirements: FR-11

- [ ] 50. Implement Ingest page with status and error UX (`app/pages/1_Ingest.py`)
  - arXiv ID text input and PDF file uploader
  - `st.status()` block with live substeps on submission
  - On completion: structured preview card with chunk/table/equation counts
  - Explicit warning banner on partial parse failure — never silent
  - Relevant requirements: FR-1, FR-11

- [ ] 51. Implement Chat page skeleton (`app/pages/2_Chat.py`)
  - Two-column layout: chat (65%) + trace panel (35%)
  - Paper multiselect, `st.chat_input`, `st.chat_message` history
  - Relevant requirements: FR-11, FR-12

- [ ] 52. Wire Chat page to in-process LangGraph streaming
  - Import LangGraph runnable directly; stream via `.stream()` / `.astream_events()`
  - Write incremental trace steps to `st.session_state` as they arrive
  - Does NOT call `/query/stream` FastAPI endpoint
  - Relevant requirements: FR-12, NFR-4

- [ ] 53. Implement equation/table rendering and revision badge
  - Equations: `st.latex()` by default; fallback to third-party KaTeX component only if needed
  - Tables: `st.dataframe()` or `st.table()` — never raw markdown
  - Show "⚠ Answer revised after verification" badge when `self_correction_applied=True`
  - Expandable citations footer per answer
  - Relevant requirements: FR-11, FR-12

- [ ] 54. Implement Paper Explorer page (`app/pages/3_Paper_Explorer.py`)
  - Left sidebar: paper selector + section/page navigator
  - Tabs: Prose, Equations, Tables, Summary
  - Equations rendered with `st.latex()`; tables as `st.dataframe()`; summary claims link to supporting chunks
  - Relevant requirements: FR-11

- [ ] 55. Implement Eval Dashboard skeleton (`app/pages/4_Eval_Dashboard.py`)
  - "Run evaluation" button triggering `/eval/run`
  - Results table: per-question RAGAS scores
  - Aggregate scores vs. target thresholds with pass/fail coloring
  - Relevant requirements: FR-15

- [ ] 56. Full manual walkthrough and fixes
  - Ingest a new paper, ask a question, watch the trace, browse Paper Explorer, run eval — all through UI
  - Fix any integration issues found
  - Relevant requirements: FR-11, FR-12, FR-13, FR-14, FR-15

- [ ] 57. Polish empty/loading/error states across all UI pages
  - Every page handles: loading state, empty state, error state explicitly
  - No silent failures or blank screens
  - Relevant requirements: FR-11, NFR-3

## Phase 7 — Evaluation & Polish

- [ ] 58. Build 15–30 question eval set (`quantinsight/eval/dataset.json`)
  - Questions across 4–6 ingested papers
  - Deliberately cover all `ChunkType`s: prose, table, equation, figure_caption
  - Include at least 5 multi-hop / multi-paper questions
  - Relevant requirements: FR-15

- [ ] 59. Implement `run_eval.py` and wire `/eval/run` endpoint
  - Run RAGAS (`faithfulness`, `context_precision`, `answer_relevancy`) against `dataset.json`
  - Output scores to stdout and write `eval/results.md` with timestamp
  - `/eval/run` API endpoint triggers this script and returns scores dict
  - Relevant requirements: FR-15, NFR-1

- [ ] 60. Run baseline eval and record results
  - Execute `run_eval.py` against full eval set
  - Record scores in `eval/results.md`
  - Check against PRD targets: faithfulness ≥ 0.85, context precision ≥ 0.85
  - Relevant requirements: FR-15

- [ ] 61. Prompt and retrieval iteration based on eval failures
  - Identify low-scoring questions; trace failures to root cause (prompt, retrieval, parsing)
  - Apply targeted fixes; re-run eval; document delta in `eval/results.md`
  - Relevant requirements: FR-7, FR-8, FR-9, FR-15

- [ ] 62. Final README pass
  - Architecture diagram, setup instructions (`git clone` + `uv pip install -e .` + `.env`)
  - Demo GIF or screenshot of ingest → chat → trace → Paper Explorer flow
  - Eval results summary with methodology note
  - Relevant requirements: NFR-5

- [ ] 63. Final CI pass and `v0.1` tag
  - Confirm all tests pass on `main`; CI green
  - Tag `v0.1`; confirm fresh clone + install + eval script runs without intervention
  - Relevant requirements: NFR-5
