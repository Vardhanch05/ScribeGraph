# Implementation Plan
## QuantInsight — Agentic Research & Context Engineering Framework

**Version:** 0.1 (Draft)
**Timeline:** 6–8 weeks, part-time solo build
**Principle:** build the data contract first, agent loop second, interfaces last — each phase should produce something runnable and testable, not just scaffolding.

---

## Phase 0 — Project Setup (Days 1–2)

- [ ] Initialize repo, `uv venv`, `uv pip install -e .`
- [ ] Set up `pyproject.toml` with dependency groups (core, dev, eval)
- [ ] Set up `.pre-commit-config.yaml` (ruff, black/ruff-format, mypy or pyright)
- [ ] Set up GitHub Actions CI (lint + pytest) — see AGENTS.md conventions
- [ ] Define repo structure (see §7 below)
- [ ] Create `.env.example` for API keys (LLM provider, LlamaParse key)

**Exit criteria:** `uv run pytest` runs (even with zero tests) and CI passes on push.

---

## Phase 1 — Data Contracts & Ingestion Core (Week 1)

**Goal:** given one arXiv paper, produce validated Pydantic objects for every chunk type. No agent, no UI yet.

- [ ] Implement all schemas from TRD §3 (`SourcePaper`, `PaperChunk`, `TableUnit`, `EquationUnit`, `Citation`, `CitedSummary`)
- [ ] Implement LlamaParse integration (`ingestion/parser.py`) — arXiv ID → PDF fetch → LlamaParse call → raw Markdown
- [ ] Add a simple `asyncio.Semaphore`-based rate limiter around LlamaParse calls (free tier: 20 requests/minute) — only matters when batch-ingesting multiple papers in a test loop, but cheap to add now and avoids confusing 429s later
- [ ] Confirm raw Markdown is persisted to the artifact store on every parse (LlamaParse caches identical re-parses within 48h for free — this is a real cost-avoidance mechanism, not just traceability)
- [ ] Implement segmentation logic (`ingestion/segmenter.py`) — raw Markdown → typed chunk objects, preserving `order_index` and page numbers
- [ ] Implement `CitedSummary` generation (single LLM call over the full paper, bounded by explicit "every claim must cite a chunk" prompt instruction)
- [ ] Write unit tests: given a known sample paper, assert expected chunk counts, at least one `EquationUnit` extracted correctly, at least one `TableUnit` with correct row/column shape

**Exit criteria:** run a CLI script (`scripts/ingest.py --arxiv-id 1706.03762`) end-to-end, inspect output objects, confidence that equations/tables survive parsing.

**Known risk to test early:** LlamaParse's actual fidelity on two-column layouts and LaTeX — validate against 2–3 real papers before building anything downstream. If fidelity is poor on certain paper styles, document the limitation rather than discovering it in week 5.

---

## Phase 2 — Storage & Retrieval (Week 2)

**Goal:** persisted, queryable knowledge base.

- [ ] Set up ChromaDB collections (`prose_chunks`, `table_chunks`, `equation_chunks`)
- [ ] Set up SQLite schema (via `sqlmodel` or raw SQL) for `SourcePaper`, `TableUnit`, `EquationUnit`, `Citation`, `CitedSummary`
- [ ] Implement embedding generation + storage on ingest
- [ ] Implement basic retrieval function: `search(query, paper_ids, chunk_types) -> list[PaperChunk | TableUnit | EquationUnit]`
- [ ] Write tests: known query against a known ingested paper returns the expected chunk

**Exit criteria:** can ingest 3–4 real papers and run manual retrieval queries from a script, spot-checking relevance.

---

## Phase 3 — LangGraph Agent Loop (Weeks 3–4)

**Goal:** the actual agentic differentiator — this is the highest-value, highest-risk phase, budget the most time here.

- [ ] Define `GraphState` (TRD §4.2)
- [ ] Implement `Planner` node (decompose query, decide retrieval strategy)
- [ ] Implement `Retriever` node (calls Phase 2 retrieval, type-aware)
- [ ] Implement `Synthesizer` node (draft answer generation with citations)
- [ ] Implement `Verifier` node (checks draft against evidence — start simple: LLM-based self-check prompt; upgrade to NLI model if time allows, mirroring your existing DeBERTa-NLI approach)
- [ ] Wire up conditional routing (revision loop, max 2 iterations)
- [ ] Add LangGraph checkpointing (SQLite-backed)
- [ ] Persist `AgentTraceStep` list per run
- [ ] Write tests: run the graph against 5 known questions, assert final answer contains expected citation IDs

**Exit criteria:** CLI script (`scripts/query.py --question "..." --paper-ids ...`) runs the full graph end-to-end and prints a `QueryResponse` with visible trace steps and at least one example where the Verifier triggers a real revision.

---

## Phase 4 — API Layer (Week 5)

**Goal:** expose Stage 1 + Stage 2 over HTTP, including streaming.

- [ ] FastAPI app skeleton, Pydantic request/response models per TRD §5
- [ ] `/ingest`, `/ingest/{id}/status`, `/papers`, `/papers/{id}` endpoints
- [ ] `/query` endpoint (synchronous)
- [ ] `/query/stream` endpoint (SSE) — reserved for **external clients only** (MCP consumers, API/Postman demos). Per TRD §8.1, the Streamlit UI does not use this endpoint — it streams the LangGraph runnable in-process instead (see Phase 6). Building this endpoint is still valuable (proves the API is genuinely consumable outside the UI), just don't treat it as the UI's data source.
- [ ] `/eval/run` endpoint
- [ ] Basic error handling middleware (never leak raw stack traces to the client; structured error responses)

**Exit criteria:** `curl`/Postman can ingest a paper and query it end-to-end without touching Python directly.

---

## Phase 5 — MCP Server Layer (Week 5–6, can run partly parallel to Phase 4)

- [ ] Implement FastMCP server exposing the four tools from TRD §6
- [ ] Test with an MCP-compatible client (e.g., Claude Desktop's MCP connector) to confirm tools are discoverable and callable
- [ ] Document tool schemas clearly (this doubles as your "AI interoperability" resume talking point)

**Exit criteria:** an external MCP client can call `ask_quantinsight` and get a valid structured response.

---

## Phase 6 — Streamlit UI (Week 6–7)

Build in the order screens are used, per App Flow doc:

- [ ] Home / Paper Library page
- [ ] Ingest page (with `st.status` live substeps)
- [ ] Chat page (chat + trace panel) — streams the LangGraph runnable **in-process** via `.stream()`/`.astream_events()`, writing incremental steps to `st.session_state` (per TRD §8.1); does not call the FastAPI SSE endpoint
- [ ] Paper Explorer page
- [ ] Eval Dashboard page

**Exit criteria:** a full manual walkthrough — ingest a new paper, ask a question, watch the trace, browse the paper explorer, run eval — all through the UI, zero direct script calls needed.

---

## Phase 7 — Evaluation & Polish (Week 7–8)

- [ ] Build the 15–30 question eval set across 4–6 papers (deliberately cover all chunk types + at least a few multi-hop/multi-paper questions)
- [ ] Run RAGAS, record baseline scores
- [ ] Iterate on prompts/retrieval based on failure cases
- [ ] Write `eval/results.md` with methodology + scores (interview/resume artifact)
- [ ] Final README pass: architecture diagram, setup instructions, demo GIF/screenshot, eval results summary
- [ ] Record a short demo video/walkthrough (optional but high-value for applications)

**Exit criteria:** repo is clone-and-run-able by a stranger following the README, with a documented eval report.

---

## 7. Repository Structure

```
quantinsight/
├── pyproject.toml
├── uv.lock
├── README.md
├── .env.example
├── .pre-commit-config.yaml
├── .github/workflows/ci.yml
├── AGENTS.md
├── docs/
│   ├── 01_PRD.md
│   ├── 02_TRD.md
│   ├── 03_APP_FLOW_UX.md
│   └── 04_IMPLEMENTATION_PLAN.md
├── quantinsight/
│   ├── __init__.py
│   ├── schemas/              # all Pydantic models (TRD §3)
│   ├── ingestion/
│   │   ├── parser.py         # LlamaParse integration
│   │   └── segmenter.py      # raw markdown -> typed chunks
│   ├── storage/
│   │   ├── chroma_store.py
│   │   └── sqlite_store.py
│   ├── agent/
│   │   ├── graph.py           # LangGraph definition
│   │   ├── nodes/
│   │   │   ├── planner.py
│   │   │   ├── retriever.py
│   │   │   ├── verifier.py
│   │   │   └── synthesizer.py
│   │   └── state.py
│   ├── api/
│   │   ├── main.py            # FastAPI app
│   │   └── routes/
│   ├── mcp_server/
│   │   └── server.py
│   └── eval/
│       ├── dataset.json       # held-out Q&A pairs
│       └── run_eval.py
├── app/                        # Streamlit UI
│   ├── Home.py
│   └── pages/
├── tests/
│   ├── test_ingestion.py
│   ├── test_retrieval.py
│   ├── test_agent_graph.py
│   └── test_api.py
└── scripts/
    ├── ingest.py
    └── query.py
```

## 8. Definition of Done (project-level)

- [ ] All Phase exit criteria met
- [ ] CI passing on `main`
- [ ] README includes architecture diagram, setup steps, and eval results
- [ ] At least one recorded demo (video or GIF) showing ingest → query → trace → explorer
- [ ] `AGENTS.md` present and accurate (see companion document)
