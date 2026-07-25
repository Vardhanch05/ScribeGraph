# Requirements — QuantInsight Core

## Overview
QuantInsight is a two-stage knowledge extraction and agentic retrieval framework for arXiv-style research papers. Stage 1 ingests and structurally parses papers; Stage 2 answers research questions via a stateful, self-correcting LangGraph agent and exposes retrieval as an MCP tool surface.

---

## Functional Requirements

### Ingestion (FR-1 – FR-5)

**FR-1** — The system shall accept an arXiv ID or a PDF file upload as ingestion inputs via the Streamlit UI.

**FR-2** — The system shall parse the submitted document via LlamaParse, producing structured Markdown that preserves reading-order layout, LaTeX equations, and table structure.

**FR-3** — The system shall segment parsed Markdown into typed knowledge units:
- `PaperChunk` (prose) with `page_number`, `section_title`, and `order_index`
- `TableUnit` with `headers`, `rows`, `caption`, and `page_number`
- `EquationUnit` with `latex`, `surrounding_context`, `equation_label`, and `page_number`

**FR-4** — The system shall generate a `CitedSummary` for each ingested paper: a bounded, evidence-linked summary where every key claim references at least one `supporting_chunk_id`.

**FR-5** — Ingestion shall be idempotent: re-ingesting the same paper ID shall update existing records rather than create duplicates.

---

### Retrieval & Reasoning (FR-6 – FR-10)

**FR-6** — The system shall accept a natural-language query against one or more ingested papers.

**FR-7** — The LangGraph agent shall determine whether a query requires single-hop retrieval (one paper, direct lookup) or multi-hop / multi-paper reasoning, and plan accordingly.

**FR-8** — Retrieval shall be type-aware: queries about equations shall preferentially surface `EquationUnit`s; queries about results/numbers shall preferentially surface `TableUnit`s; general prose queries shall surface `PaperChunk`s.

**FR-9** — The agent shall perform a self-correction pass: a draft answer is checked against retrieved evidence by the Verifier node; unsupported claims or contradictions trigger a retrieval revision loop (max 2 iterations).

**FR-10** — Every answer shall include traceable citations linking each claim to a specific chunk ID, page number, and source paper.

---

### Interfaces (FR-11 – FR-14)

**FR-11** — The Streamlit UI shall support PDF upload, arXiv ID entry, chat-style Q&A, and rendered LaTeX/table display in answers.

**FR-12** — The Streamlit UI shall display a live agent execution trace (node name, tool calls, inputs/outputs per step) as the agent runs, via in-process LangGraph `.stream()` / `.astream_events()` — not via the FastAPI SSE endpoint.

**FR-13** — A FastAPI backend shall expose REST endpoints for ingestion and query, including a `/query/stream` SSE endpoint for external clients.

**FR-14** — An MCP server (FastMCP) shall expose the following tools for external agent consumers:
- `search_papers(query, paper_ids) -> list[PaperChunk]`
- `get_paper_summary(paper_id) -> CitedSummary`
- `get_equation_context(paper_id, equation_label) -> EquationUnit`
- `ask_quantinsight(query, paper_ids) -> QueryResponse`

---

### Evaluation (FR-15)

**FR-15** — The system shall include a held-out eval set of 15–30 hand-written Q&A pairs across 4–6 ingested papers (covering all four chunk types and multi-hop questions), runnable via `quantinsight/eval/run_eval.py`, producing RAGAS scores for faithfulness, context precision, and answer relevancy.

---

## Non-Functional Requirements

**NFR-1 — Latency**
- Single-paper query: < 20s end-to-end
- Multi-paper multi-hop query: < 45s end-to-end
- Ingestion per paper: < 90s (LlamaParse-dependent; log actual time)

**NFR-2 — Type safety**
- 100% of cross-boundary data (API request/response, MCP tool signatures, LangGraph state) shall be typed Pydantic v2 models. No bare `dict` or `Any` across module boundaries.

**NFR-3 — Reliability**
- Every external call (LlamaParse, LLM API, ChromaDB) shall be wrapped with retry logic (max 2 retries) and explicit exception handling. Silent failures are not acceptable.

**NFR-4 — Observability**
- Every agent run shall produce a persisted `AgentTraceStep` list, queryable after the fact. Trace data must not be discarded after streaming.

**NFR-5 — Reproducibility**
- `uv.lock` shall be committed. A fresh `git clone` + `uv pip install -e .` shall be sufficient to run the eval script without manual intervention.

**NFR-6 — Rate limit compliance**
- LlamaParse ingestion shall use an `asyncio.Semaphore`-based rate limiter to stay within the 20 requests/minute free-tier cap when batch-ingesting multiple papers.

**NFR-7 — Idempotent artifact caching**
- Raw LlamaParse Markdown output shall be persisted to `/artifacts/{paper_id}/raw.md` on every parse to avoid re-billing within the 48-hour LlamaParse cache window and to support traceability/debugging.

---

## Correctness Properties (for Property-Based Testing)

**CP-1 — Chunk coverage:** For any successfully ingested paper, the union of all extracted chunks shall account for all pages in the source document (no page silently dropped).

**CP-2 — Equation round-trip:** For any `EquationUnit`, the `latex` field shall be parseable as valid LaTeX (KaTeX-renderable) — i.e., the extraction process shall not produce malformed LaTeX strings.

**CP-3 — Table structural integrity:** For any `TableUnit`, every row in `rows` shall have `len(row) == len(headers)` — no ragged rows from parsing.

**CP-4 — CitedSummary evidence linkage:** For any `CitedSummary`, every `chunk_id` in `supporting_chunk_ids` shall reference an existing `PaperChunk` belonging to the same `paper_id`.

**CP-5 — Idempotency:** Ingesting the same `arxiv_id` twice shall produce exactly one `SourcePaper` record (no duplicates) and the same set of chunk IDs as the first ingestion.

**CP-6 — Answer citation validity:** For any `QueryResponse`, every UUID in `citations` shall reference an existing chunk (PaperChunk, TableUnit, or EquationUnit) in the storage layer.

**CP-7 — Verifier loop bound:** The agent graph shall never execute more than 2 retrieval-verification loop iterations for any single query (hard cap enforced in graph routing logic).

**CP-8 — Trace completeness:** For any completed agent run, `GraphState.trace` shall contain exactly one `AgentTraceStep` per node execution, in execution order, with no gaps.
