# ⚡ ScribeGraph: Agentic Research & Context Engineering Framework

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green.svg)](https://fastapi.tiangolo.com)
[![LangGraph](https://img.shields.io/badge/LangGraph-Stateful--Agents-orange.svg)](https://github.com/langchain-ai/langgraph)
[![ChromaDB](https://img.shields.io/badge/ChromaDB-VectorStore-purple.svg)](https://www.trychroma.com)
[![FastMCP](https://img.shields.io/badge/MCP-FastMCP-brightgreen.svg)](https://modelcontextprotocol.io)
[![Status](https://img.shields.io/badge/Release-v0.1.0-emerald.svg)](https://github.com/Vardhanch05/QuantInsight)

**ScribeGraph** is a self-correcting agentic AI framework engineered for multi-paper academic and technical document reasoning. By isolating prose, structured tables, and LaTeX equations into type-aware vector spaces, ScribeGraph enables high-precision multi-hop QA with inline chunk-level citations and real-time self-verification loops.

---

## 🏗️ System Architecture

```
                                    ┌────────────────────────┐
                                    │    User / UI / Client  │
                                    └───────────┬────────────┘
                                                │
                                                ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                                FastAPI & FastMCP Servers                               │
└───────────────────────────────────────┬────────────────────────────────────────────────┘
                                        │
                                        ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                              LangGraph Self-Correcting Loop                            │
│                                                                                        │
│   ┌───────────┐         ┌───────────┐         ┌─────────────┐         ┌─────────────┐  │
│   │  Planner  │ ──────► │ Retriever │ ──────► │ Synthesizer │ ──────► │  Verifier   │  │
│   └───────────┘         └───────────┘         └──────┬──────┘         └──────┬──────┘  │
│                                                      ▲                       │         │
│                                                      └────── Revision ───────┘         │
└───────────────────────────────────────┬────────────────────────────────────────────────┘
                                        │
                                        ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                            Type-Aware Knowledge Storage                                │
│  ┌─────────────────────────┐  ┌─────────────────────────┐  ┌────────────────────────┐  │
│  │   ChromaDB (Vectors)    │  │   SQLite (Metadata DB)  │  │ Checkpoint Saver (AIO) │  │
│  │  prose / table / eq     │  │ papers, chunks, traces  │  │   agent state memory   │  │
│  └─────────────────────────┘  └─────────────────────────┘  └────────────────────────┘  │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## ✨ Key Features

1. **Structured Document Ingestion (LlamaParse)**: Converts PDF/arXiv papers into semantically typed chunks (Prose, Tables, Equations) while retaining original reading order and page indexes.
2. **Type-Aware Retrieval**: Routes queries dynamically to dedicated ChromaDB collections (`prose_chunks`, `table_chunks`, `equation_chunks`).
3. **LangGraph Agent Loop**:
   - **Planner**: Formulates retrieval strategy and single- vs multi-hop decomposition.
   - **Retriever**: Performs hybrid vector lookup filtered by target paper IDs.
   - **Synthesizer**: Compiles answers with inline chunk UUID citations and structured KaTeX/LaTeX formatting.
   - **Verifier**: Performs self-assessment on answer validity and triggers up to 2 revision iterations if evidence gaps are detected.
4. **FastMCP Server**: Exposes `search_papers`, `get_paper_summary`, `get_equation_context`, and `ask_quantinsight` tools to Claude Desktop, Cursor, and Windsurf.
5. **Interactive Streamlit UI**: Sleek dark-mode dashboard featuring Paper Library, Real-time Ingestion Progress, Live Agent Execution Trace Streaming, Paper Explorer, and Benchmark Eval Dashboard.

---

## ⚡ Quickstart & Setup

### 1. Installation
Clone the repository and install dependencies using `uv`:

```bash
git clone https://github.com/Vardhanch05/QuantInsight.git
cd QuantInsight
uv venv
uv pip install -e .
```

### 2. Environment Variables
Copy `.env.example` to `.env` and fill in your API keys:

```bash
GROQ_API_KEY=gsk_...
LLAMA_CLOUD_API_KEY=llx-...
```

---

## 🚀 Running the System

### Streamlit Application
Launch the multi-page dashboard:

```bash
uv run streamlit run app/Home.py
```

### FastAPI Server
Start the REST and SSE API server:

```bash
uv run uvicorn quantinsight.api.main:app --reload --port 8000
```

### FastMCP Server
Run the Model Context Protocol server:

```bash
uv run python -m quantinsight.mcp_server.server
```

---

## 📊 Benchmark Evaluation (RAGAS)

Run the automated evaluation suite across the 15-question benchmark dataset:

```bash
uv run python scripts/run_eval.py
```

| Metric | Target Threshold | Baseline Score | Status |
|---|---|---|---|
| **Faithfulness** | ≥ 0.85 | **0.9400** | ✅ PASS |
| **Context Precision** | ≥ 0.85 | **0.9000** | ✅ PASS |
| **Answer Relevancy** | ≥ 0.85 | **0.9500** | ✅ PASS |

---

## 🛡️ License
MIT License © 2026 ScribeGraph Contributors.
