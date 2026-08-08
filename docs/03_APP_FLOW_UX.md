# App Flow & UI/UX Design
## ScribeGraph — Agentic Research & Context Engineering Framework

**Version:** 0.1 (Draft)
**Scope:** Streamlit UI only (per project constraint — no HTML/CSS/JS/React)

---

## 1. Design Principles

- **Show the reasoning, not just the answer.** The trace viewer is a first-class feature, not a debug afterthought — it's the single most interview-demoable part of the app.
- **Preserve fidelity.** Equations render as real math (KaTeX), tables render as real tables — never raw markdown/LaTeX source dumped as plain text in the final answer view. Note: prefer Streamlit's native `st.latex()` as the default renderer where possible — it works out-of-the-box with no extra dependency risk. Only reach for a third-party component like `streamlit-katex` if `st.latex()` proves insufficient for a specific case (e.g., inline math mixed with prose in a single block); third-party Streamlit components can lag behind Streamlit/Python version updates, so treat them as an enhancement, not a foundation.
- **Minimal but not bare.** Streamlit's default look is fine; don't over-invest in visual polish given the "pure Python, no frontend framework" constraint — invest polish in the trace/citation UX instead, since that's the functional differentiator.

## 2. App Structure (Streamlit multi-page)

```
app/
├── Home.py                     # landing / paper library view
├── pages/
│   ├── 1_Ingest.py             # upload PDF / enter arXiv ID
│   ├── 2_Chat.py               # main Q&A interface with trace viewer
│   ├── 3_Paper_Explorer.py     # browse a single paper's structured chunks/tables/equations
│   └── 4_Eval_Dashboard.py     # view RAGAS scores over time
```

## 3. Screen-by-Screen Flow

### 3.1 Home — Paper Library
**Purpose:** entry point, shows what's already ingested.

- A table/grid of ingested papers: title, authors, arXiv ID, ingestion date, chunk/equation/table counts.
- Each row has a "Chat about this paper" button → jumps to Chat page pre-filtered to that paper.
- Empty state: clear CTA "No papers yet — ingest your first paper" → links to Ingest page.

### 3.2 Ingest Page
**Purpose:** get a paper into the system.

**Flow:**
1. User chooses input mode: `arXiv ID` (text input) or `Upload PDF` (file uploader).
2. On submit → call `POST /ingest`, show a `st.status()` block with live sub-steps:
   - "Fetching/reading document…"
   - "Parsing structure (LlamaParse)…"
   - "Extracting equations and tables…"
   - "Generating summary…"
   - "Storing embeddings…"
3. On completion: show a structured preview card — title, author, page count, counts of extracted `PaperChunk` / `TableUnit` / `EquationUnit`, and the generated `CitedSummary`.
4. Error state: if parsing fails or confidence is low on any section, show an explicit warning banner (not a silent partial success) — e.g., "3 tables could not be fully parsed — view raw source."

### 3.3 Chat Page (core experience)
**Purpose:** ask questions, see grounded answers, see the agent think.

**Layout — two-column:**

**Left column (main chat, ~65% width):**
- Paper selector (multiselect — supports single or multi-paper queries)
- Standard chat input at bottom (`st.chat_input`)
- Chat history rendered as message bubbles (`st.chat_message`)
- Assistant responses render:
  - Prose answer text
  - Inline equations via KaTeX rendering (not raw LaTeX source)
  - Any tables as real `st.dataframe`/`st.table`, not markdown text
  - A citations footer: numbered references linking to source chunk/page, expandable to show the original excerpt

**Right column (agent trace panel, ~35% width, collapsible):**
- Live step-by-step trace as the agent runs (via SSE from `/query/stream`):
  - `Planner` → shows the decomposed plan
  - `Retriever` → shows what was searched and what came back (chunk previews)
  - `Verifier` → shows whether a contradiction/unsupported claim was flagged, and if a revision loop triggered
  - `Synthesizer` → final answer assembly
- Each step is a collapsible `st.expander` so the panel doesn't overwhelm by default, but full detail is one click away — this is the "look, I can show you exactly how it reasoned" interview moment.
- A small badge if self-correction was triggered: "⚠ Answer revised after verification" — makes the self-correction loop visible and provable, not just a backend implementation detail.

### 3.4 Paper Explorer Page
**Purpose:** let a user (or interviewer) browse the structured extraction directly, independent of chat — proves the parsing quality on its own.

- Left sidebar: paper selector + section/page navigator
- Main panel tabs:
  - **Prose** — `PaperChunk`s in reading order
  - **Equations** — `EquationUnit`s rendered with KaTeX, each showing surrounding context
  - **Tables** — `TableUnit`s rendered as real tables with captions
  - **Summary** — the `CitedSummary` with each key claim linking to its supporting chunk(s)

This page is arguably the best single screen to show an interviewer, since it directly demonstrates the core differentiator (structure preservation) without needing to explain the agent at all.

### 3.5 Eval Dashboard
**Purpose:** show measured quality, not just claimed quality.

- Button: "Run evaluation" → triggers `/eval/run`, shows a spinner, then results
- Results table: per-question RAGAS scores (faithfulness, context precision, answer relevancy)
- Summary metrics at top: aggregate scores vs. target thresholds (from PRD §5), pass/fail coloring
- Historical run log (if you store timestamped results) — a simple line chart of scores over time as the system improves, which is a great "I iterated and measured" resume/interview artifact

## 4. Key UX States to Handle Explicitly

| State | UX Treatment |
|---|---|
| Ingestion in progress | `st.status` with live substeps, not a bare spinner |
| Ingestion partial failure | Explicit warning banner naming what failed, never silent |
| Query in progress | Trace panel populates live via streaming; main chat shows a "thinking" placeholder bubble |
| Self-correction triggered | Visible badge/notice on the final answer |
| No relevant evidence found | Explicit "I couldn't find supporting evidence for this in the ingested papers" — never a hallucinated answer dressed as confident |
| Multi-paper query | Trace panel shows retrieval broken out per paper, so it's clear the agent actually consulted more than one source |

## 5. Interaction Notes

- Use `st.session_state` to persist chat history and selected papers across reruns (Streamlit's default rerun model requires this discipline).
- SSE streaming into Streamlit: **decided approach (see TRD §8.1)** — the Streamlit UI does NOT consume the FastAPI SSE endpoint. Instead, it imports the LangGraph runnable directly and streams via `.stream()`/`.astream_events()` in-process, writing steps into `st.session_state` as they arrive. The FastAPI `/query/stream` SSE endpoint is reserved for external clients only (MCP consumers, API integrators). This sidesteps Streamlit's known difficulty sustaining long-lived async SSE connections entirely, rather than working around it.
- Keep the trace panel's default state collapsed-but-visible on desktop widths, and consider hiding it behind a toggle on narrow viewports if you test on mobile — not a primary target, but don't let it break outright.
