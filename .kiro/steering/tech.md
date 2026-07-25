---
inclusion: always
---

# QuantInsight — Tech Stack & Conventions

## Stack
| Layer | Technology |
|---|---|
| UI | Streamlit + `st.latex()` (KaTeX via third-party only as fallback) |
| Backend API | FastAPI + Uvicorn |
| Validation | Pydantic v2 |
| Parsing | LlamaParse |
| Orchestration | LangGraph (stateful graph, SQLite checkpointing) |
| Vector store | ChromaDB (one collection per chunk type) |
| Metadata store | SQLite via `sqlmodel` or raw `sqlite3` |
| Interop | MCP via FastMCP / official Python SDK |
| Package mgmt | `uv` (`uv.lock` committed) |
| Async | `asyncio` for all I/O |
| Evaluation | RAGAS |

## Code Conventions
- **Typing is mandatory.** Every function signature and cross-module data structure is typed. No bare `dict`/`Any` across module boundaries — use Pydantic models in `quantinsight/schemas/`.
- **Pydantic v2 only.** Use `model_config`, `Field`, v2 validators. No v1-style `class Config`.
- **Async by default for I/O.** LlamaParse, LLM, ChromaDB, and FastAPI routes are `async def` unless there's a documented reason not to.
- **No new UI frameworks.** UI is Streamlit only. No React/HTML/JS/CSS files.
- **Every external call is wrapped.** LlamaParse, LLM API, ChromaDB — all get retry (max 2) + explicit exception handling. No silent failures.
- **Every agent run is traced.** All changes to `quantinsight/agent/` must preserve the `AgentTraceStep` logging contract.

## Streaming Architecture
- Streamlit UI streams the LangGraph runnable **in-process** via `.stream()`/`.astream_events()` — does NOT consume the FastAPI SSE endpoint.
- FastAPI `/query/stream` SSE endpoint is for **external clients only** (MCP consumers, API integrators).

## LlamaParse Rate Limits
- Free tier: 10,000 credits/month; 20 requests/minute.
- Use `asyncio.Semaphore` + short sleep when batch-ingesting to stay under 20 req/min.
- Raw Markdown artifact store (`/artifacts/{paper_id}/raw.md`) avoids re-billing on repeated parses (48h cache window).

## Testing
- New ingestion logic → fixture paper in `tests/fixtures/`, assert expected chunk counts/types.
- New agent node → test in `tests/test_agent_graph.py` asserting output shape.
- New API route → test in `tests/test_api.py` using FastAPI `TestClient`.
- CI must stay green on `main`.
