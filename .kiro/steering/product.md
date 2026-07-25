---
inclusion: always
---

# QuantInsight — Product Context

QuantInsight is a two-stage knowledge extraction and agentic retrieval framework for arXiv-style research papers. It is a portfolio project targeting quant researchers and ML engineers who need precision answers grounded in dense academic literature (equations, tables, citations).

## Core Problem
Standard vector RAG fails on research papers due to:
- Two-column layouts read out of order
- LaTeX equations garbled or dropped
- Multi-column tables losing row/column relationships
- Citation hierarchies invisible to flat-chunk retrieval

## What This System Does
1. Parses arXiv papers preserving structure (layout, math, tables, citations) via LlamaParse
2. Stores structure in typed, queryable form (not flat text blobs)
3. Answers research questions via a stateful, self-correcting LangGraph agent
4. Exposes retrieval as a reusable tool via MCP for external agent consumers

## Non-Goals (explicitly out of scope)
- No multi-tenant auth, billing, or horizontal scaling
- Not a general-purpose PDF tool — arXiv-style papers only
- No training/fine-tuning — uses existing LLM APIs only
- No continuous crawler — per-paper ingestion only

## Success Metrics
| Metric | Target |
|---|---|
| Answer faithfulness (RAGAS) | ≥ 0.85 |
| Context precision (RAGAS) | ≥ 0.85 |
| Equation preservation rate | ≥ 95% |
| Table structural integrity | ≥ 90% |
| Single-paper query latency | < 20s |
| Multi-paper multi-hop latency | < 45s |
