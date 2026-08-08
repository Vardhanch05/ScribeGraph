# Technical Requirements Document (TRD)
## ScribeGraph — Agentic Research & Context Engineering Framework

**Version:** 0.1 (Draft)
**Companion to:** 01_PRD.md

---

## 1. System Architecture Overview

Two-stage architecture, consistent with the PRD's framing:

```
┌─────────────────────────────────────────────────────────────────┐
│                         STAGE 1: EXTRACTION                       │
│                                                                     │
│  arXiv ID / PDF Upload                                            │
│         │                                                          │
│         ▼                                                          │
│  LlamaParse (structure-preserving parse → Markdown)                │
│         │                                                          │
│         ▼                                                          │
│  Segmentation Layer (Pydantic schema mapping)                      │
│         │                                                          │
│    ┌────┼────────────┬──────────────┐                             │
│    ▼    ▼             ▼              ▼                             │
│ PaperChunk  TableUnit  EquationUnit  CitedSummary                  │
│    │    │             │              │                             │
│    ▼    ▼             ▼              ▼                             │
│  ChromaDB (embeddings)      SQLite / JSON Artifact Store           │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      STAGE 2: RETRIEVAL & REASONING                │
│                                                                     │
│              FastAPI (REST) ◄──────────► MCP Server (FastMCP)      │
│                       │                                             │
│                       ▼                                             │
│              LangGraph Agent Graph                                 │
│      ┌──────────┬────────────┬─────────────┬──────────────┐       │
│      │ Planner  │ Retriever  │  Verifier    │ Synthesizer  │       │
│      │  Node    │   Node     │  (NLI/self-  │    Node      │       │
│      │          │            │  check) Node │              │       │
│      └──────────┴────────────┴─────────────┴──────────────┘       │
│                       │                                             │
│                       ▼                                             │
│              Streamlit UI (chat + trace viewer + KaTeX render)     │
└─────────────────────────────────────────────────────────────────┘
```

## 2. Technology Stack (confirmed per project constraints)

| Layer | Technology | Purpose |
|---|---|---|
| UI | Streamlit + KaTeX (via `streamlit-katex` or custom HTML component within Streamlit) | Upload, chat, trace visualization, math rendering |
| Backend API | FastAPI + Uvicorn | Async REST endpoints, SSE streaming of agent trace |
| Validation | Pydantic v2 | All schemas, request/response models, LangGraph state typing |
| Parsing | LlamaParse | PDF → structured Markdown with layout/math/table preservation |
| Orchestration | LangGraph | Stateful multi-agent graph, checkpointing, reflection loop |
| Vector store | ChromaDB | Embedding storage + semantic search |
| Metadata/state store | SQLite (via `sqlmodel` or raw `sqlite3`) + JSON artifact files | Thread state, ingestion metadata, structured Pydantic outputs |
| Interop | MCP (FastMCP / official Python SDK) | Expose retrieval/query as tools for external agent consumers |
| Env/package mgmt | `uv` | Fast, reproducible dependency management |
| Async | `asyncio` | Non-blocking ingestion and query paths |
| Evaluation | RAGAS | Faithfulness / context precision scoring against eval set |

## 3. Data Models (Pydantic v2 Schemas)

These are the core "knowledge unit" contracts — get these right first, everything downstream depends on them.

```python
from __future__ import annotations
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field
from uuid import UUID, uuid4


class ChunkType(str, Enum):
    PROSE = "prose"
    TABLE = "table"
    EQUATION = "equation"
    FIGURE_CAPTION = "figure_caption"


class SourcePaper(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    arxiv_id: str | None = None
    title: str
    authors: list[str]
    source_url: str | None = None
    ingested_at: datetime = Field(default_factory=datetime.utcnow)
    raw_markdown_path: str  # path to LlamaParse output, kept for traceability
    page_count: int


class PaperChunk(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    paper_id: UUID
    chunk_type: ChunkType
    content: str  # markdown/latex-preserving text
    page_number: int
    section_title: str | None = None
    order_index: int  # preserves reading order within the paper
    embedding_id: str | None = None  # pointer into ChromaDB


class TableUnit(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    paper_id: UUID
    chunk_id: UUID  # links back to the PaperChunk it was extracted from
    caption: str | None = None
    headers: list[str]
    rows: list[list[str]]
    page_number: int


class EquationUnit(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    paper_id: UUID
    chunk_id: UUID
    latex: str
    surrounding_context: (
        str  # sentence(s) immediately before/after, for retrieval relevance
    )
    equation_label: str | None = None  # e.g. "(3)" if numbered in source
    page_number: int


class Citation(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    paper_id: UUID
    cited_text: str  # the in-text citation marker/context
    cited_work_raw: str  # raw reference string from bibliography
    resolved_arxiv_id: str | None = None  # if resolvable


class CitedSummary(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    paper_id: UUID
    summary: str
    key_claims: list[str]
    supporting_chunk_ids: list[UUID]  # every claim must trace to at least one chunk
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    model_used: str


class AgentTraceStep(BaseModel):
    step_index: int
    node_name: str  # e.g. "planner", "retriever", "verifier", "synthesizer"
    input_summary: str
    output_summary: str
    tool_calls: list[dict] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class QueryResponse(BaseModel):
    answer: str
    citations: list[UUID]  # PaperChunk / TableUnit / EquationUnit ids used
    trace: list[AgentTraceStep]
    self_correction_applied: bool
    confidence_note: str | None = None
```

## 4. LangGraph Agent Design

### 4.1 Graph nodes

| Node | Responsibility | Reuses |
|---|---|---|
| **Planner** | Decomposes the query; decides single-hop vs. multi-hop/multi-paper; picks retrieval strategy | New |
| **Retriever** | Calls ChromaDB with type-aware filtering (e.g., prioritize `EquationUnit` for math questions) | New, but conceptually similar to your existing metadata-filtered retrieval |
| **Verifier** | Checks draft claims against retrieved chunks for contradiction/unsupported statements | Reuse pattern from your NLI contradiction-detection work — swap DeBERTa-NLI for an LLM-based or hybrid NLI check here |
| **Synthesizer** | Produces the final answer with citations, renders equations/tables inline | New |
| **Reflection/Router** | Decides whether Verifier's flags require looping back to Retriever or Synthesizer, or whether the answer is ready to return | New — this is the actual "agentic" control flow, not just a linear chain |

### 4.2 State schema (LangGraph `TypedDict` / Pydantic state)

```python
class GraphState(BaseModel):
    query: str
    paper_ids: list[UUID]
    plan: str | None = None
    retrieved_chunks: list[PaperChunk] = []
    retrieved_tables: list[TableUnit] = []
    retrieved_equations: list[EquationUnit] = []
    draft_answer: str | None = None
    verification_notes: list[str] = []
    needs_revision: bool = False
    final_answer: QueryResponse | None = None
    trace: list[AgentTraceStep] = []
```

### 4.3 Control flow

```
START → Planner → Retriever → Synthesizer(draft) → Verifier
                                                        │
                                          ┌─────────────┴─────────────┐
                                    needs_revision=True         needs_revision=False
                                          │                             │
                                          ▼                             ▼
                                     Retriever (loop,               Synthesizer(final)
                                     max 2 iterations)                    │
                                                                          ▼
                                                                         END
```
- Checkpointing: use LangGraph's built-in checkpointer (SQLite-backed) so a query thread can be paused/resumed/inspected — this is also what powers the live trace viewer in Streamlit.
- Max iteration guard: hard cap of 2 retrieval-verification loops to avoid infinite correction cycles (log if cap is hit — this is itself a useful eval signal).

## 5. API Specification (FastAPI)

| Endpoint | Method | Purpose |
|---|---|---|
| `/ingest` | POST | Accepts arXiv ID or PDF upload; triggers Stage 1 pipeline; returns `SourcePaper.id` |
| `/ingest/{paper_id}/status` | GET | Poll ingestion status (parsing can take time) |
| `/query` | POST | Accepts `{query: str, paper_ids: list[UUID]}`; returns `QueryResponse` |
| `/query/stream` | POST | Same as above, but Server-Sent Events streaming the agent trace as it executes |
| `/papers` | GET | List ingested papers with metadata |
| `/papers/{paper_id}` | GET | Retrieve full `SourcePaper` + summary |
| `/eval/run` | POST | Trigger RAGAS evaluation against the stored eval set, return scores |

All request/response bodies are typed with the Pydantic models above — no untyped dicts across the API boundary.

## 6. MCP Server Layer

Expose a minimal, well-scoped tool surface — not everything the internal agent can do:

| MCP Tool | Description |
|---|---|
| `search_papers(query: str, paper_ids: list[str] | None) -> list[PaperChunk]` | Semantic search across ingested papers |
| `get_paper_summary(paper_id: str) -> CitedSummary` | Retrieve the stored structured summary |
| `get_equation_context(paper_id: str, equation_label: str) -> EquationUnit` | Look up a specific numbered equation and its surrounding context |
| `ask_quantinsight(query: str, paper_ids: list[str]) -> QueryResponse` | Full agentic query — lets an external agent delegate a whole research question |

This is what makes the system a genuine *framework*, not just an app — any external MCP-compatible client (Claude Desktop, another LangGraph app, etc.) can use it as a tool.

## 7. Storage Design

- **ChromaDB collection(s):** one collection per chunk type (`prose_chunks`, `table_chunks`, `equation_chunks`) so type-aware retrieval filtering is a native collection choice, not a metadata filter hack — simpler and faster for a solo-scale project.
- **SQLite:** stores `SourcePaper`, `TableUnit`, `EquationUnit`, `Citation`, `CitedSummary` records (relational integrity — a `TableUnit` always references a valid `paper_id`).
- **JSON artifact store:** raw LlamaParse output per paper (`/artifacts/{paper_id}/raw.md`) kept for traceability/debugging — if parsing quality is ever questioned, you can point to the exact source markdown.
- **LangGraph checkpoints:** SQLite-backed checkpointer, separate DB file from the main metadata store to keep concerns isolated.

## 8. Non-Functional Requirements

| Requirement | Target |
|---|---|
| Query latency (single paper) | < 20s end-to-end |
| Query latency (multi-paper, multi-hop) | < 45s end-to-end |
| Ingestion time per paper | < 90s (dependent on LlamaParse response time — log actual, don't over-promise) |
| Error handling | Every external call (LlamaParse, LLM API, ChromaDB) wrapped with retry (max 2) + graceful degradation, never a silent failure |
| Type safety | 100% of cross-boundary data (API, MCP, LangGraph state) is a typed Pydantic model — no raw dicts |
| Observability | Every agent run produces a persisted `AgentTraceStep` list, queryable after the fact, not just streamed and discarded |
| Reproducibility | `uv.lock` committed; fresh clone + `uv pip install -e .` should run the eval script without manual intervention |

## 8.1 Streaming Architecture Decision (SSE risk + fallback)

Streamlit's rerun-on-interaction execution model doesn't natively sustain a long-lived async SSE connection the way a persistent frontend framework would. Two viable approaches, in priority order:

1. **Primary (recommended): in-process LangGraph streaming.** When the query originates from the Streamlit UI, import and invoke the LangGraph runnable directly inside the Streamlit session (not through the FastAPI HTTP layer) and consume it via LangGraph's native `.stream()` or `.astream_events()` iterator, writing incremental trace steps into `st.session_state` as they arrive. This avoids the SSE-into-Streamlit integration problem entirely for the primary UI path.
2. **Secondary: FastAPI `/query/stream` SSE endpoint.** Keep this for **external clients only** (MCP consumers, API integrators, `curl`/Postman demos) where a real HTTP client can consume SSE natively. Do not force the Streamlit UI through this path.

This means the FastAPI SSE endpoint and the Streamlit trace panel are two independent consumers of the same underlying LangGraph `.stream()` capability, not one feeding the other. Document this explicitly in the API section so it's clear `/query/stream` is not dead code — it serves a different audience (Part of TRD §5, §6).

## 8.2 LlamaParse Quota & Rate Limit Details (corrected)

Earlier planning assumed a flat "1,000 pages/day" free tier. Current (verified) structure is different and matters for pipeline design:

- **Free tier: 10,000 credits/month**, not a daily page cap. Actual page throughput depends on parsing tier — roughly ~3,300 pages/month at the cost-effective tier, or ~10,000 pages/month at the fast tier. For a portfolio-scale corpus (tens of papers), this is comfortably sufficient regardless of tier choice.
- **Rate limit: 20 requests/minute on the free tier**, independent of the monthly credit cap. This is the more likely thing to actually trip during development — e.g., batch-ingesting several papers in a quick test loop.
- **Caching is free:** re-parsing the same file within 48 hours costs zero credits. This makes the raw-Markdown artifact store (TRD §7) doubly valuable — it's both a traceability record and a way to avoid accidental re-billing during iterative debugging.
- **Implication for `ingestion/parser.py` (Phase 1):** add a small delay/queue (or a semaphore-based rate limiter) around LlamaParse calls when ingesting more than a couple of papers in sequence, to stay under 20 req/min. A simple `asyncio.Semaphore` + short sleep is sufficient at this scale — no need for a sophisticated rate-limiting library.

## 9. Evaluation Plan

- Build a **held-out eval set** of 15–30 Q&A pairs across 4–6 ingested papers (mix of factual, table-lookup, equation-lookup, and multi-hop questions — cover all four `ChunkType`s deliberately).
- Run **RAGAS** (`faithfulness`, `context_precision`, `answer_relevancy`) as an automated script (`scripts/run_eval.py`), output a markdown report checked into the repo (`eval/results.md`) with a timestamp — this becomes both a dev tool and a resume artifact.
- Track **self-correction rate** separately (not a RAGAS metric) — how often does the Verifier node actually trigger a revision loop, and did it improve or degrade the answer on manual review of a sample.

## 10. Out of Scope for TRD (deferred / stretch)

- Multi-tenant auth, rate limiting per user
- Horizontal scaling / distributed ChromaDB
- Continuous arXiv crawling (batch/on-demand ingestion only)
- Fine-tuning any model (API-based LLMs only)
