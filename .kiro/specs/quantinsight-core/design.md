# Design — QuantInsight Core

## Overview

Two-stage architecture. Stage 1 (Extraction) parses arXiv PDFs into typed knowledge units via LlamaParse and stores them in ChromaDB + SQLite. Stage 2 (Retrieval & Reasoning) answers queries via a stateful LangGraph agent graph and exposes the same retrieval primitives as an MCP tool surface.

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         STAGE 1: EXTRACTION                      │
│                                                                   │
│  arXiv ID / PDF Upload                                            │
│         │                                                         │
│         ▼                                                         │
│  LlamaParse (structure-preserving parse → Markdown)               │
│         │                                                         │
│         ▼                                                         │
│  Segmentation Layer (Pydantic schema mapping)                     │
│         │                                                         │
│    ┌────┼────────────┬──────────────┐                            │
│    ▼    ▼             ▼              ▼                            │
│ PaperChunk  TableUnit  EquationUnit  CitedSummary                 │
│    │    │             │              │                            │
│    ▼    ▼             ▼              ▼                            │
│  ChromaDB (embeddings)      SQLite + Artifact Store               │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      STAGE 2: RETRIEVAL & REASONING              │
│                                                                   │
│         FastAPI (REST) ◄──────────► MCP Server (FastMCP)         │
│                  │                                                │
│                  ▼                                                │
│         LangGraph Agent Graph                                     │
│   ┌──────────┬────────────┬─────────────┬──────────────┐        │
│   │ Planner  │ Retriever  │  Verifier   │ Synthesizer  │        │
│   └──────────┴────────────┴─────────────┴──────────────┘        │
│                  │                                                │
│                  ▼                                                │
│         Streamlit UI (chat + trace viewer + LaTeX render)        │
└─────────────────────────────────────────────────────────────────┘
```

---

## Data Models (`quantinsight/schemas/`)

All cross-boundary data uses Pydantic v2. No bare `dict` or `Any` across module boundaries.

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
    raw_markdown_path: str  # path to /artifacts/{paper_id}/raw.md
    page_count: int


class PaperChunk(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    paper_id: UUID
    chunk_type: ChunkType
    content: str
    page_number: int
    section_title: str | None = None
    order_index: int
    embedding_id: str | None = None  # pointer into ChromaDB


class TableUnit(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    paper_id: UUID
    chunk_id: UUID
    caption: str | None = None
    headers: list[str]
    rows: list[list[str]]
    page_number: int


class EquationUnit(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    paper_id: UUID
    chunk_id: UUID
    latex: str
    surrounding_context: str
    equation_label: str | None = None
    page_number: int


class Citation(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    paper_id: UUID
    cited_text: str
    cited_work_raw: str
    resolved_arxiv_id: str | None = None


class CitedSummary(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    paper_id: UUID
    summary: str
    key_claims: list[str]
    supporting_chunk_ids: list[UUID]
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    model_used: str


class AgentTraceStep(BaseModel):
    step_index: int
    node_name: str
    input_summary: str
    output_summary: str
    tool_calls: list[dict] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class QueryResponse(BaseModel):
    answer: str
    citations: list[UUID]
    trace: list[AgentTraceStep]
    self_correction_applied: bool
    confidence_note: str | None = None
```

---

## LangGraph Agent Design (`quantinsight/agent/`)

### Graph State

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
    revision_count: int = 0  # enforces CP-7 max-2 loop cap
    final_answer: QueryResponse | None = None
    trace: list[AgentTraceStep] = []
```

### Nodes

| Node | File | Responsibility |
|---|---|---|
| Planner | `nodes/planner.py` | Decompose query; decide single-hop vs multi-hop; write `plan` to state |
| Retriever | `nodes/retriever.py` | Type-aware ChromaDB query; populate `retrieved_chunks/tables/equations` |
| Synthesizer | `nodes/synthesizer.py` | Draft answer with inline citations; every claim must reference a chunk ID |
| Verifier | `nodes/verifier.py` | LLM self-check of draft vs evidence; set `needs_revision` + `verification_notes` |

Every node appends an `AgentTraceStep` to `GraphState.trace` before returning (CP-8 contract).

### Control Flow

```
START → Planner → Retriever → Synthesizer(draft) → Verifier
                                                        │
                                          ┌─────────────┴──────────────┐
                                  needs_revision=True          needs_revision=False
                                  revision_count < 2           OR revision_count >= 2
                                          │                             │
                                          ▼                             ▼
                                     Retriever (loop)           Synthesizer(final) → END
```

- Hard cap: `revision_count` is incremented on each loop. Router blocks further revision once it reaches 2 (CP-7).
- Checkpointing: SQLite-backed LangGraph checkpointer, separate DB file from the main metadata store.
- No-evidence path: if Retriever returns empty results, Synthesizer emits a structured "no supporting evidence found" response rather than hallucinating.

---

## Storage Design (`quantinsight/storage/`)

### ChromaDB
Three collections — one per chunk type — so type-aware retrieval is a native collection choice, not a metadata filter. Embeddings are generated locally using the `BAAI/bge-small-en-v1.5` model via `sentence-transformers`:

| Collection | Contents |
|---|---|
| `prose_chunks` | `PaperChunk` embeddings (prose) |
| `table_chunks` | `TableUnit` embeddings (caption + headers) |
| `equation_chunks` | `EquationUnit` embeddings (latex + surrounding context) |

### SQLite
Relational store for structured metadata and relationships:
- Tables: `source_papers`, `paper_chunks`, `table_units`, `equation_units`, `citations`, `cited_summaries`
- Foreign key: every `TableUnit` / `EquationUnit` references a valid `paper_id`
- Separate DB file for LangGraph checkpoints

### Artifact Store
- Path: `/artifacts/{paper_id}/raw.md`
- Created on every LlamaParse call
- Prevents re-billing within the 48h LlamaParse cache window (NFR-7)

---

## API Design (`quantinsight/api/`)

| Endpoint | Method | Request | Response |
|---|---|---|---|
| `/ingest` | POST | `{arxiv_id?: str, pdf?: UploadFile}` | `{paper_id: UUID}` |
| `/ingest/{paper_id}/status` | GET | — | `{status: str, paper?: SourcePaper}` |
| `/papers` | GET | — | `list[SourcePaper]` |
| `/papers/{paper_id}` | GET | — | `SourcePaper` + `CitedSummary` |
| `/query` | POST | `{query: str, paper_ids: list[UUID]}` | `QueryResponse` |
| `/query/stream` | POST | `{query: str, paper_ids: list[UUID]}` | SSE stream of `AgentTraceStep` — external clients only |
| `/eval/run` | POST | — | RAGAS scores dict |

All request/response bodies are Pydantic v2 models. Error responses are structured (never raw stack traces).

---

## MCP Server Design (`quantinsight/mcp_server/server.py`)

FastMCP server exposing four tools. Internal implementations are shared with the Retriever node — no duplicated logic.

| Tool | Signature | Description |
|---|---|---|
| `search_papers` | `(query: str, paper_ids: list[str] \| None) -> list[PaperChunk]` | Semantic search across ingested papers |
| `get_paper_summary` | `(paper_id: str) -> CitedSummary` | Retrieve stored structured summary |
| `get_equation_context` | `(paper_id: str, equation_label: str) -> EquationUnit` | Look up a numbered equation + surrounding context |
| `ask_quantinsight` | `(query: str, paper_ids: list[str]) -> QueryResponse` | Full agentic query delegation |

---

## Streamlit UI Design (`app/`)

### Pages
| Page | File | Purpose |
|---|---|---|
| Home | `Home.py` | Paper library — list ingested papers, CTA to ingest |
| Ingest | `pages/1_Ingest.py` | arXiv ID / PDF upload; `st.status` live substeps |
| Chat | `pages/2_Chat.py` | Chat + two-column trace panel |
| Paper Explorer | `pages/3_Paper_Explorer.py` | Browse chunks/tables/equations per paper |
| Eval Dashboard | `pages/4_Eval_Dashboard.py` | RAGAS scores, historical trend |

### Streaming (Chat page)
The Chat page imports the LangGraph runnable **in-process** and streams via `.stream()` / `.astream_events()`, writing steps into `st.session_state`. It does **not** consume `/query/stream` — that endpoint is reserved for external clients (FR-12, TRD §8.1).

### Rendering
- Equations: `st.latex()` by default; third-party KaTeX component only as fallback for inline math mixed with prose
- Tables: `st.dataframe()` / `st.table()` — never raw markdown text
- Citations: expandable footer per answer, linking chunk ID → page → source paper

---

## Ingestion Pipeline (`quantinsight/ingestion/`)

### `parser.py`
1. Accept arXiv ID → fetch PDF from arXiv, or accept direct PDF upload
2. Call LlamaParse (async, with `asyncio.Semaphore` rate limiter, max 20 req/min)
3. Persist raw Markdown to `/artifacts/{paper_id}/raw.md`
4. Return raw Markdown string

### `segmenter.py`
1. Parse raw Markdown → identify prose blocks, LaTeX delimiters, table blocks
2. Produce typed objects: `PaperChunk`, `TableUnit`, `EquationUnit`
3. Assign `order_index` preserving reading order; record `page_number` from LlamaParse metadata
4. Flag low-confidence extractions (don't silently drop — surface warning via API/UI)

### `CitedSummary` generation
Single LLM call over the full paper with a structured-output prompt requiring every key claim to cite at least one `chunk_id` from the segmented set.

### Idempotency (FR-5 / CP-5)
On re-ingest of the same `arxiv_id`: look up existing `SourcePaper` by `arxiv_id`, update in place, reconcile chunk sets (upsert by stable ID), never insert duplicates.

---

## Evaluation (`quantinsight/eval/`)

- `dataset.json`: 15–30 hand-written Q&A pairs across 4–6 papers; covers all `ChunkType`s + multi-hop questions
- `run_eval.py`: runs RAGAS (`faithfulness`, `context_precision`, `answer_relevancy`) against the stored eval set; outputs scores to stdout and `eval/results.md`
- Self-correction rate tracked separately (logged in `AgentTraceStep` — not a RAGAS metric)

---

## Non-Functional Design Decisions

| Concern | Decision |
|---|---|
| Rate limiting | `asyncio.Semaphore(20)` + short sleep in `parser.py`; applied whenever >1 paper ingested in sequence |
| Retry logic | Decorator-based retry (max 2) on all LlamaParse, LLM, and ChromaDB calls; raises structured exception on exhaustion |
| Trace persistence | `AgentTraceStep` list written to SQLite alongside the LangGraph checkpoint — survives process restart |
| Secret management | `.env` (gitignored); `.env.example` documents all required keys; no key hardcoded anywhere |
| LLM & Embeddings | Groq-only API (`GROQ_API_KEY`) for all LLM inference; Local `sentence-transformers` (`BAAI/bge-small-en-v1.5`) for embedding generation |
| CI | GitHub Actions: `ruff check`, `pyright`/`mypy`, `pytest` — must pass on every push to `main` |
