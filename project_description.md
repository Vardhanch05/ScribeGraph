# QuantInsight: Agentic Research & Context Engineering Framework

QuantInsight is a state-of-the-art, two-stage technical document ingestion, retrieval, and agentic reasoning framework optimized for dense academic papers (such as arXiv PDFs). Rather than utilizing a traditional, flat-chunk "naive RAG" pipeline which fails on technical layouts, mathematical notation, and structured tables, QuantInsight parses, stores, and queries technical documents by preserving their original layouts, math context, and tabular structure. Queries are answered using a stateful, self-correcting agent loop orchestrated via LangGraph.

---

## 1. The Core Problem & Motivation

Standard vector Retrieval-Augmented Generation (RAG) systems fail on technical documents (arXiv papers, technical reports, financial sheets) in several predictable ways:
1. **Layout Scrambling:** Two-column PDFs are frequently read horizontally by standard PDF parsers, scrambling reading order.
2. **Mathematical Notation Flattening:** LaTeX equations get flattened into garbled Unicode or dropped completely, destroying mathematical assertions.
3. **Tabular Data Destruction:** Multi-column results tables lose row/column associations when converted to simple plain text, preventing accurate lookup.
4. **Citation Ignorance:** Citation hierarchies are invisible to flat-chunk retrievers, rendering the system unable to distinguish between a paper's own findings and the cited works of others.

**QuantInsight** solves these challenges by treating technical PDFs as structured data rather than unstructured text blobs. It parses, segments, and stores documents as distinct semantic units and queries them using a self-correcting reflection loop.

---

## 2. System Architecture

QuantInsight operates in two primary stages: **Stage 1 (Structure-Preserving Ingestion & Extraction)** and **Stage 2 (Agentic Retrieval & Reasoning)**.

```mermaid
graph TD
    %% Stage 1: Extraction & Ingestion
    subgraph Stage1["STAGE 1: Extraction & Ingestion"]
        Input[arXiv ID / PDF Upload] --> Parser[LlamaParse: PDF to Structure-Preserved MD]
        Parser --> Cache{Artifact Cache Check}
        Cache -- "< 48 Hours" --> LocalCache[Load Cached Markdown]
        Cache -- "Cache Miss" --> CallLlamaParse[Call LlamaParse API]
        CallLlamaParse --> StoreCache[Save to /artifacts/paper_id/raw.md]
        
        LocalCache & StoreCache --> SegLayer[Segmentation Layer]
        SegLayer --> Chunks[PaperChunk Prose]
        SegLayer --> Tables[TableUnit Tables]
        SegLayer --> Equations[EquationUnit Math]
        
        Chunks --> Embed[Local Embeddings: BAAI/bge-small-en-v1.5]
        Embed --> Chroma[ChromaDB prose_chunks / table_chunks / equation_chunks]
        
        SegLayer --> SQLiteStore[SQLite: SourcePaper, PaperChunkDb, TableUnitDb, EquationUnitDb, CitedSummaryDb]
        Chunks & Tables & Equations --> SummaryLLM[Groq CitedSummary Generator]
        SummaryLLM --> SQLiteStore
    end

    %% Stage 2: Retrieval & Reasoning
    subgraph Stage2["STAGE 2: Retrieval & Agentic Reasoning"]
        API[FastAPI REST API / MCP FastMCP Server] --> Graph[LangGraph Agent Loop]
        
        subgraph LangGraph["LangGraph State Machine"]
            Planner[Planner Node] --> Retriever[Retriever Node]
            Retriever --> Synthesizer[Synthesizer Node - Draft]
            Synthesizer --> Verifier[Verifier Node]
            Verifier --> Router{needs_revision?}
            Router -- "Yes (Count < 2)" --> Retriever
            Router -- "No / Max Loops Hit" --> FinalSynth[Synthesizer Node - Final]
        end
        
        Chroma & SQLiteStore <--> Retriever
        FinalSynth --> UI[Streamlit UX: Chat, Trace Expander, Explorer]
    end
```

---

## 3. Technology Stack

QuantInsight utilizes a curated stack prioritizing performance, local execution of lightweight components, and structured APIs:

| Layer | Component / Tool | Function / Trade-off |
|---|---|---|
| **Core Structure** | Python 3.11+ / Pydantic v2 | Standard type-safety, contract enforcement, and serialization validation. |
| **PDF Extraction** | LlamaParse | Structure-aware parsing that converts complex multi-column layouts into markdown with math/tables intact. |
| **Embeddings** | `sentence-transformers` (`BAAI/bge-small-en-v1.5`) | Local embedding model run inside the thread, avoiding external API latency and cost. |
| **Vector DB** | ChromaDB (Persistent Local Client) | Dynamic, type-separated vector collections (`prose_chunks`, `table_chunks`, `equation_chunks`). |
| **Metadata DB** | SQLite (via `sqlmodel`) | Structured relational tables with foreign keys and cascade deletions. |
| **Agent Engine** | LangGraph | Stateful multi-agent graph with built-in SQLite checkpointing and routing. |
| **LLM Provider** | Groq (Llama-3.1-70B-Versatile) | Extremely high-speed inference for planner, synthesizer, summary, and verification tasks. |
| **UI** | Streamlit + KaTeX | Fast, pure-Python dashboard supporting chat UI, math rendering, and expandable reasoning traces. |
| **Integration** | FastAPI / FastMCP (Model Context Protocol) | Dual interface allowing execution either via REST requests or as tools exposed to AI clients like Claude Desktop. |
| **Package Mgmt** | `uv` | High-speed, reproducible environment and lockfile generation. |
| **Evaluation** | RAGAS | Framework for quantitative validation of retrieval precision and answer faithfulness. |

---

## 4. Stage 1: Structure-Preserving Ingestion & Segmentation

```
PDF File / arXiv ID ──► LlamaParse ──► Raw Markdown ──► Segmenter ──► Database Persistence
```

### 4.1 Fetching & Caching Wrapper (`quantinsight/ingestion/parser.py`)
- **arXiv Retrieval:** Downloads PDFs directly from `https://arxiv.org/pdf/{arxiv_id}` using a resilient HTTP client.
- **LlamaParse Integration:** Passes PDFs to the LlamaParse API.
- **Rate-Limit Semaphore:** Wraps the external LlamaParse call in an `asyncio.Semaphore(20)` and applies a `3.0s` sleep spacing, preventing `429 Too Many Requests` errors on free-tier accounts.
- **48-Hour Caching:** Writes parsed markdown to `/artifacts/{paper_id}/raw.md` and tracks arXiv mappings in a `cache.json` file. If a paper is re-ingested within 48 hours, it bypasses the LlamaParse call, saving API credits.

### 4.2 Document Segmentation (`quantinsight/ingestion/segmenter.py`)
The raw Markdown returned by the parser is sliced into structured objects by the segmenter:
- **`PaperChunk` (Prose & Figure Captions):** Segments the markdown by section headers and splits blocks into manageable paragraphs.
- **`TableUnit` (Tabular Data):** Detects markdown tables, parses headers, extracts cells, and converts them to a structured matrix (`list[list[str]]`). Pydantic validators verify that every row matches the header length, throwing explicit warnings if tables are misaligned.
- **`EquationUnit` (Math):** Uses regex to isolate mathematical expressions wrapped in `$$` or `$`. It extracts the LaTeX string alongside its surrounding sentences (preceding and succeeding blocks) to preserve context for semantic search.

### 4.3 Cited Summary Generation (`quantinsight/ingestion/summary.py`)
Before saving the paper, a specialized prompt sends the extracted chunks to Groq. The model compiles a **`CitedSummary`** containing:
1. A brief overview of the paper.
2. Key scientific claims.
3. An array of `supporting_chunk_ids` mapping every claim back to a specific prose chunk.

### 4.4 Idempotent Pipelines (`quantinsight/ingestion/pipeline.py`)
Ingestion is completely idempotent. If a paper is submitted that matches an existing `arxiv_id`:
1. It updates the parent `SourcePaper` metadata record.
2. It deletes all existing child records in SQLite (chunks, tables, equations, citations, summaries).
3. It calls `delete_paper_embeddings` to flush existing vector embeddings in ChromaDB.
4. It inserts the newly parsed chunks and generates fresh embeddings, keeping the DB clear of duplicates.

---

## 5. Stage 2: Storage & Relational Design

QuantInsight stores structural data using a hybrid database architecture: relational metadata in SQLite and semantic vectors in ChromaDB.

```
                          ┌──────────────────────┐
                          │     SourcePaper      │
                          └──────────┬───────────┘
                                     │
             ┌───────────────────────┼────────────────────────┐
             ▼                       ▼                        ▼
     ┌───────────────┐       ┌───────────────┐        ┌───────────────┐
     │  PaperChunk   │       │  CitationDb   │        │ CitedSummary  │
     └───────┬───────┘       └───────────────┘        └───────────────┘
             │
      ┌──────┴──────┐
      ▼             ▼
┌───────────┐ ┌───────────┐
│ TableUnit │ │ Equation  │
└───────────┘ └───────────┘
```

### 5.1 SQLite Relational Schema (`quantinsight/storage/sqlite_store.py`)
Using `SQLModel`, QuantInsight creates several structured tables:
- **`source_papers`**: Stores paper details (`arxiv_id`, `title`, `authors`, `raw_markdown_path`, `page_count`).
- **`paper_chunks`**: Stores individual text blocks. Includes `embedding_id` which acts as the join-key to ChromaDB vector documents.
- **`table_units`**: Stores tables with JSON headers and row matrices. Linked via foreign key with `ON DELETE CASCADE` to both `source_papers` and `paper_chunks`.
- **`equation_units`**: Stores mathematical equations (`latex`, `surrounding_context`, `equation_label`).
- **`citations`**: Tracks citation metadata.
- **`cited_summaries`**: Holds LLM-generated summaries and claims.

### 5.2 ChromaDB Collections (`quantinsight/storage/chroma_store.py`)
Rather than keeping a single vector store, QuantInsight segments embeddings into three collections:
1. **`prose_chunks`**: Semantic vectors of textual sections.
2. **`table_chunks`**: Generated from a synthesized table text representation: `Table caption: {caption}. Headers: {headers}.`
3. **`equation_chunks`**: Generated from the formula and its context: `Equation: {latex}. Context: {context}.`

This partitioning allows Stage 2 retrieval to query only relevant subsets (e.g. searching only math models when asked about formulas), reducing vector noise.

---

## 6. Stage 3: The LangGraph Agent Loop

QuantInsight leverages a multi-node state machine designed in LangGraph to handle retrieval and answer generation:

```
        Planner
           │
           ▼
     ┌─ Retriever ◄────────────────┐
     │     │                       │
     │     ▼                       │
     │ Synthesizer (Draft)         │ (Yes, count < 2)
     │     │                       │
     │     ▼                       │
     └─► Verifier ──► needs_revision? 
                       │
                       └───► No / Max Loops ──► Final Synthesizer ──► END
```

### 6.1 State Definition (`quantinsight/agent/state.py`)
All nodes mutate a shared `GraphState` object:
- `query` (str): The user's prompt.
- `paper_ids` (list[UUID]): Target papers for the search scope.
- `plan` (str): Generated decomposition steps.
- `retrieved_chunks` / `retrieved_tables` / `retrieved_equations`: Arrays containing retrieved elements.
- `draft_answer` (str): Intermediate answer.
- `verification_notes` (list[str]): Feedback from the verification node.
- `needs_revision` (bool): Instruction to loop.
- `revision_count` (int): Number of correction loops run (hard capped at 2).
- `final_answer` (QueryResponse): Final serialized response.
- `trace` (list[AgentTraceStep]): Appended logs for UI visualization.

### 6.2 Agent Nodes
1. **Planner (`planner.py`):** Uses Llama-3-70B with structured outputs to decide if the query requires a single-hop lookup or a multi-hop comparison. Writes a structured retrieval plan.
2. **Retriever (`retriever.py`):** Converts the plan into specific type queries. It routes searches to specific ChromaDB collections.
3. **Synthesizer (`synthesizer.py`):** Consolidates the evidence. It requires inline citations (e.g., `[chunk_id]`) for every factual statement and outputs tables and equations in pristine formatting.
4. **Verifier (`verifier.py`):** Acts as a validation gate. It performs an LLM-based NLI check comparing the `draft_answer` against the original `retrieved_*` inputs. If it detects a contradiction, hallucination, or missing formula, it sets `needs_revision = True` and writes specific correction instructions.

---

## 7. Interfaces & API Layer

QuantInsight provides three access interfaces to accommodate different development and user workflows.

### 7.1 FastAPI REST Layer (`quantinsight/api/main.py`)
Exposes HTTP endpoints for standard API interactions:
- `POST /ingest`: Accepts an arXiv ID or a PDF multipart upload. Triggers background ingestion and returns a `paper_id`.
- `GET /ingest/{paper_id}/status`: Provides processing updates.
- `GET /papers`: Returns metadata for all processed files.
- `POST /query`: Submits a query to the LangGraph state machine, executing synchronously.
- `POST /query/stream`: Establishes a Server-Sent Events (SSE) connection, streaming the execution trace (`AgentTraceStep` steps) in real-time to external clients.

### 7.2 Model Context Protocol Server (`quantinsight/mcp_server/server.py`)
Implemented using the Model Context Protocol (FastMCP), this server exposes QuantInsight capabilities as standard tools to external LLM clients (such as Claude Desktop or custom developer systems):
- `search_papers(query, paper_ids)`: Performs semantic retrieval across collections.
- `get_paper_summary(paper_id)`: Fetches SQLite summaries.
- `get_equation_context(paper_id, equation_label)`: Queries specific formulas by label.
- `ask_quantinsight(query, paper_ids)`: Executes the full LangGraph agent loop.

### 7.3 Streamlit Multi-Page UI (`app/`)
- **Home (`Home.py`):** Visualizes the ingested library with metadata grids and chunk/equation counters.
- **Ingest (`pages/1_Ingest.py`):** Features file upload, arXiv entry, and a live `st.status()` block tracking segmentation.
- **Chat (`pages/2_Chat.py`):** The primary chat window. Displays math using LaTeX syntax and structures tables as dataframes. Includes a side-collateral panel that prints the live execution steps (e.g., Planner, Retriever, Verifier logs) and displays a "Revised" warning badge if the Verifier triggered a self-correction loop.
- **Paper Explorer (`pages/3_Paper_Explorer.py`):** A document explorer showing prose, equations, and tables in isolation.

---

## 8. Evaluation Framework (RAGAS)

QuantInsight evaluates context quality using a programmatic script (`quantinsight/eval/run_eval.py`):

```
                   Evaluation Pipeline
                   
  Test Dataset        QuantInsight          RAGAS Evaluation       Output Report
(dataset.json) ──► Agent Execution ──► (Faithfulness, Precision) ──► results.md
```

### 8.1 Evaluated Metrics
- **Faithfulness:** Assesses whether the generated response is grounded in the retrieved chunks (target threshold: `≥ 0.85`).
- **Context Precision:** Measures whether relevant chunks are ranked higher during collection searches (target threshold: `≥ 0.85`).
- **Self-Correction Rate:** Tracked by logging how often the Verifier triggers the revision branch and measuring the quality improvement between the draft and final answers.

---

## 9. Code Standards & Architecture Guidelines

To maintain clean and testable development, the framework enforces several coding constraints:
1. **Type Safety:** 100% typing is required. No untyped dictionaries or raw `Any` variables are allowed across module boundaries.
2. **Pydantic v2 Models:** Data contracts must use Pydantic v2 parameters (`model_config`, `Field`) to ensure clean serialization.
3. **Resilient APIs:** Every external service call (LlamaParse, Groq LLM, ChromaDB) must be wrapped with exception handling and a retry mechanism (typically managed using `tenacity` decorators with exponential backoffs).
4. **Execution Trace Compliance:** Any modification to agent nodes must preserve the `AgentTraceStep` logging contract to keep trace panels in the UI populated.

---

## 10. Repository Directory Structure

```
QuantInsight/
├── .env.example                 # Environment configuration template
├── .gitignore                   # File exclusions
├── .pre-commit-config.yaml      # Formatting/Linting pre-commit hooks
├── pyproject.toml               # Poetry/Hatch project declaration
├── uv.lock                      # Fixed uv dependency tree
├── README.md                    # Scaffold details
├── project_description.md       # Full documentation (This File)
├── AGENTS.md                    # Core agent system conventions
├── docs/                        # Specifications & Plans
│   ├── 01_PRD.md
│   ├── 02_TRD.md
│   ├── 03_APP_FLOW_UX.md
│   ├── 04_IMPLEMENTATION_PLAN.md
│   ├── COMMIT_SCHEDULE.md
│   └── HANDOFF.md
├── quantinsight/                # Source package
│   ├── __init__.py
│   ├── schemas/
│   │   └── models.py            # Shared Pydantic data models
│   ├── ingestion/
│   │   ├── parser.py            # PDF downloading, LlamaParse wrapper, caching
│   │   ├── segmenter.py         # Markdown structuring & parser alignment
│   │   ├── summary.py           # LLM paper summary generator
│   │   └── pipeline.py          # Pipeline coordinator (idempotent re-ingestion)
│   ├── storage/
│   │   ├── sqlite_store.py      # SQLite SQLModel tables and DB helpers
│   │   └── chroma_store.py      # ChromaDB embeddings saver/remover
│   ├── agent/
│   │   ├── graph.py             # LangGraph state machine builder
│   │   ├── state.py             # LangGraph shared GraphState Pydantic schema
│   │   └── nodes/               # Graph execution nodes (planner, retriever...)
│   ├── api/
│   │   └── main.py              # FastAPI application server
│   ├── mcp_server/
│   │   └── server.py            # Model Context Protocol tools definitions
│   └── eval/
│       └── run_eval.py          # RAGAS evaluator runner script
├── app/                         # Streamlit application UI
│   ├── Home.py
│   └── pages/
│       ├── 1_Ingest.py
│       ├── 2_Chat.py
│       ├── 3_Paper_Explorer.py
│       └── 4_Eval_Dashboard.py
├── scripts/                     # Developer CLI Scripts
│   ├── ingest.py                # Command line ingestion tool
│   └── query.py                 # Command line query tool
└── tests/                       # Pytest unit testing suite
    ├── test_ingestion.py
    ├── test_segmenter.py
    ├── test_pipeline.py
    ├── test_storage.py
    └── test_summary.py
```

---

## 11. Quickstart & Usage Instructions

### 11.1 Installation
Initialize the environment and install dependencies:
```bash
# Set up virtual environment and install project packages
uv venv
source .venv/bin/activate
uv pip install -e ".[dev,eval]"
```

### 11.2 Environment Variables
Create a `.env` file in the root directory:
```env
LLAMA_CLOUD_API_KEY=your_llamaparse_key
GROQ_API_KEY=your_groq_api_key
```

### 11.3 Execution Commands

- **Run Tests:**
  ```bash
  uv run pytest
  ```

- **Run Linting & Formatting Check:**
  ```bash
  uv run ruff check .
  uv run ruff format --check
  ```

- **Command-Line Ingestion:**
  ```bash
  uv run python scripts/ingest.py --arxiv-id 1706.03762
  ```

- **Command-Line Querying:**
  ```bash
  uv run python scripts/query.py --question "Explain the self-attention equation" --paper-ids <uuid>
  ```

- **Start API Server:**
  ```bash
  uv run uvicorn quantinsight.api.main:app --reload
  ```

- **Start Streamlit UI:**
  ```bash
  uv run streamlit run app/Home.py
  ```
