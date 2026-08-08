# Product Requirements Document (PRD)
## ScribeGraph — Agentic Research & Context Engineering Framework
*(working title — naming TBD)*

**Version:** 0.1 (Draft)
**Owner:** Vardhan Chilakamarri
**Status:** Planning

---

## 1. Problem Statement

Quantitative researchers, ML engineers, and students need to stay current with dense academic literature (arXiv papers, technical reports). Standard vector RAG systems fail on this content in specific, reproducible ways:

- **Two-column layouts** get read out of order when naively OCR'd or PDF-text-extracted, scrambling sentences.
- **LaTeX equations** get flattened into garbled Unicode or dropped entirely, destroying the technical meaning of a claim.
- **Multi-column tables** (common in results sections) lose their row/column relationships when converted to plain text.
- **Citation hierarchies** (which claim cites which prior work, and how directly) are invisible to flat-chunk retrieval, so a system can't distinguish "this paper's own finding" from "a claim borrowed from a cited paper."

The result: existing RAG tools give confidently wrong or incomplete answers about quantitative/technical papers — exactly the audience (quant researchers, ML practitioners) who need precision most.

## 2. Goal

Build a **two-stage knowledge extraction and context-engineering framework** that:
1. Parses arXiv-style papers while preserving structure (layout, math, tables, citations).
2. Stores that structure in typed, queryable form (not flat text blobs).
3. Answers research questions through a **stateful, self-correcting agent**, not a single-pass retrieve-and-generate call.
4. Exposes retrieval as a **reusable tool** other agents/systems can call via MCP, not just a standalone chatbot.

## 3. Non-Goals (explicitly out of scope)

- Not a production SaaS — no multi-tenant auth, billing, or horizontal scaling.
- Not a general-purpose PDF tool — optimized specifically for research-paper structure (arXiv-style), not arbitrary business documents.
- Not a training/fine-tuning project — uses existing LLM APIs, does not train custom models.
- Not a continuous crawler — ingestion is triggered per-paper (upload or arXiv ID), not a background pipeline pulling new papers automatically (may be a stretch goal, not core scope).

## 4. Target User / Persona

**Primary:** A quant researcher or ML engineer (like yourself) who wants to ask precise, evidence-grounded questions across a small curated set of papers (e.g., "how do these 3 papers define regret bounds differently?") and get an answer that respects the original math/table structure rather than a garbled paraphrase.

**Secondary (for the resume story):** An interviewer/recruiter evaluating whether the builder understands context engineering, structured parsing, and agentic system design — not just "call an LLM with a vector store."

## 5. Success Metrics

Because this is a portfolio project, "success" = demonstrable, measurable quality, not user growth. Concrete targets:

| Metric | Target | Method |
|---|---|---|
| Answer faithfulness | ≥ 0.85 | RAGAS `faithfulness` on a hand-built eval set |
| Context precision | ≥ 0.85 | RAGAS `context_precision` |
| Equation preservation rate | ≥ 95% of equations in source render correctly as LaTeX in retrieved chunks | Manual spot-check + automated regex/KaTeX-render validation on a sample |
| Table structural integrity | ≥ 90% of table cells correctly mapped to row/column on a sample of 10 papers | Manual comparison to source PDF |
| Agent self-correction rate | Measurable — track how often the reflection step actually changes the draft answer | Logged in execution trace |
| End-to-end query latency | < 20s for a single-paper query, < 45s for multi-paper multi-hop | Logged per request |

## 6. Core Features (Functional Requirements)

### 6.1 Ingestion
- FR-1: User can submit an arXiv ID or upload a PDF via Streamlit.
- FR-2: System parses the document via LlamaParse into structured Markdown preserving layout order, LaTeX, and tables.
- FR-3: System segments parsed content into typed units: `PaperChunk` (prose), `TableUnit` (tables), `EquationUnit` (math), each with page/position metadata.
- FR-4: System generates a `CitedSummary` — a bounded, evidence-linked summary of the paper — as a first-class stored artifact, not just a cache.
- FR-5: Ingestion is idempotent — re-ingesting the same paper ID updates rather than duplicates.

### 6.2 Retrieval & Reasoning
- FR-6: User can ask a natural-language question against one or more ingested papers.
- FR-7: System (via LangGraph agent) plans whether the question needs single-hop retrieval or multi-hop/multi-paper reasoning.
- FR-8: Retrieval respects structural type — e.g., a question about "the loss function" should preferentially surface `EquationUnit`s, not just prose chunks that happen to mention "loss."
- FR-9: System performs a self-correction pass: draft answer is checked against retrieved evidence before being returned; contradictions or unsupported claims are flagged or revised.
- FR-10: Every answer includes traceable citations back to the specific chunk/page/paper it came from.

### 6.3 Interfaces
- FR-11: Streamlit UI supports PDF upload, chat-style Q&A, and rendered LaTeX/table display in answers.
- FR-12: Streamlit UI shows a live agent execution trace (which node ran, what tool was called, what came back) — not just the final answer.
- FR-13: FastAPI exposes REST endpoints for ingestion and query (so the system isn't UI-locked).
- FR-14: An MCP server exposes retrieval and query functions as callable tools for external agents (e.g., Claude Desktop, another LangGraph app).

### 6.4 Evaluation
- FR-15: A held-out eval set (15–30 hand-written Q&A pairs across a handful of ingested papers) with RAGAS scoring, runnable as a script.

## 7. User Stories

- *As a researcher*, I want to ask "what assumption does Theorem 2 rely on?" and get an answer that correctly quotes the equation, not a paraphrase that drops a variable.
- *As a researcher*, I want to compare claims across two papers ("do these two papers agree on the sample complexity bound?") and see where they diverge.
- *As an interviewer*, I want to watch the agent's execution trace live to understand *how* it reasoned, not just see a final answer.
- *As an external developer*, I want to call ScribeGraph's retrieval function as an MCP tool from my own agent without needing its UI.

## 8. Constraints & Assumptions

- Assumes access to LLM API (Claude or OpenAI) with reasonable rate limits for a solo dev project.
- Assumes LlamaParse free tier (10,000 credits/month, ~3,300–10,000 pages depending on parsing tier) is sufficient for expected paper volume (small, curated corpus — tens of papers, not thousands). Free tier is also capped at 20 requests/minute — a non-issue for interactive use, but relevant if batch-ingesting several papers at once during dev/testing.
- Solo-developer timeline: 1–2 months, part-time.
- No production deployment required — local + optionally a lightweight cloud demo (e.g., Streamlit Community Cloud) for interview demos.

## 9. Risks

| Risk | Mitigation |
|---|---|
| LlamaParse doesn't perfectly preserve all equations/tables | Build validation step; fall back gracefully with confidence flag rather than silently failing |
| Scope creep (MCP + LangGraph + RAGAS + Streamlit all at once) | Sequence build order strictly — see Implementation Plan; UI and MCP layer come after core pipeline is proven |
| Small eval set limits statistical confidence | Be explicit in documentation that this is a portfolio-scale eval, not a production benchmark — matches how you should represent it in interviews |
