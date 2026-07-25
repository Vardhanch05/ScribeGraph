---
inclusion: always
---

# QuantInsight — Repository Structure

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
│   │   ├── graph.py          # LangGraph definition
│   │   ├── nodes/
│   │   │   ├── planner.py
│   │   │   ├── retriever.py
│   │   │   ├── verifier.py
│   │   │   └── synthesizer.py
│   │   └── state.py
│   ├── api/
│   │   ├── main.py           # FastAPI app
│   │   └── routes/
│   ├── mcp_server/
│   │   └── server.py
│   └── eval/
│       ├── dataset.json      # held-out Q&A pairs
│       └── run_eval.py
├── app/                      # Streamlit UI
│   ├── Home.py
│   └── pages/
│       ├── 1_Ingest.py
│       ├── 2_Chat.py
│       ├── 3_Paper_Explorer.py
│       └── 4_Eval_Dashboard.py
├── tests/
│   ├── fixtures/
│   ├── test_ingestion.py
│   ├── test_retrieval.py
│   ├── test_agent_graph.py
│   └── test_api.py
└── scripts/
    ├── ingest.py
    └── query.py
```

## Module Responsibilities
- `quantinsight/schemas/` — single source of truth for all Pydantic models; downstream consumers (storage, API, MCP, agent state) import from here, never redefine
- `quantinsight/ingestion/` — Stage 1: parse → segment → summarize; no agent logic here
- `quantinsight/storage/` — ChromaDB + SQLite persistence; no business logic, only read/write
- `quantinsight/agent/` — LangGraph graph definition, nodes, and state; depends on storage but not on API or UI
- `quantinsight/api/` — FastAPI app; thin HTTP layer over agent and storage
- `quantinsight/mcp_server/` — FastMCP server; reuses same underlying tool functions as the agent's Retriever node
- `app/` — Streamlit UI; streams the LangGraph runnable in-process, does not call the FastAPI SSE endpoint
- `tests/` — mirrors `quantinsight/` structure; fixtures in `tests/fixtures/`
