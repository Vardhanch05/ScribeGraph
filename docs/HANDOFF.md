# HANDOFF.md — QuantInsight Session Log

**Purpose:** Antigravity's agent context may not persist between sessions. This file is the single source of truth for "where we left off" — read it at the start of every session, update it at the end of every session, before every commit round.

**Rule:** never start a new Antigravity session without attaching this file. Never end a session without updating it.

---

## Current Status

- **Day:** Day 2
- **Phase:** Phase 1 — Data Contracts & Ingestion Core
- **Last completed task:** Task 6 — Implement Citation, CitedSummary, AgentTraceStep, and QueryResponse schemas
- **Next task up:** Task 7 — Implement LlamaParse client wrapper (ingestion/parser.py)
- **Blockers / open questions:** None

---

## Commit Log

*Append one row per commit, in order. This is your ground truth — more reliable than trusting the agent's memory or Git log alone, since it also captures the "why," not just the diff.*

| Date | Task # | Commit hash (short) | Commit message | Notes |
|---|---|---|---|---|
| 2026-07-25 | 1 | a7e2929 | chore: initialize repo, uv venv, and pyproject.toml | Initialized project scaffolding, uv.lock, and .gitignore |
| 2026-07-25 | 2 | fb68ab4 | ci: setup pre-commit config and github actions ci | Added .pre-commit-config.yaml, .github/workflows/ci.yml, and dummy test |
| 2026-07-25 | 3 | 78df107 | chore: create .env.example and repo scaffolding | Added .env.example and created module stubs based on structure.md |
| 2026-07-25 | 1/3 | 3d61ca1 | chore: pivot to Groq-only LLM + local embeddings [retroactive task-1/3 fix] | Retroactive architecture shift to Groq and sentence-transformers |
| 2026-07-25 | 4 | 790a6af | feat(schemas): implement SourcePaper and PaperChunk data models [task-4] | Added ChunkType, SourcePaper, and PaperChunk models to schemas/models.py |
| 2026-07-26 | 5 | 95f75f3 | feat(schemas): implement TableUnit and EquationUnit data models [task-5] | Added TableUnit with row-length validation and EquationUnit models |
| 2026-07-26 | 6 | 3683943 | feat(schemas): implement Citation, CitedSummary, AgentTraceStep, and QueryResponse data models [task-6] | Added Citation, CitedSummary, AgentTraceStep, and QueryResponse schemas |

---

## Decisions Log

*Anything decided mid-build that isn't already in `docs/` or `.kiro/specs/` — deviations, tradeoffs, things you discovered. Keep entries short. If a decision is significant enough to affect future tasks, also update the relevant steering/spec file, don't just log it here and forget.*

| Date | Decision | Why | Affects |
|---|---|---|---|
| 2026-07-25 | Pivoted from OpenAI to Groq-only LLM (`GROQ_API_KEY`) + local `sentence-transformers` (`BAAI/bge-small-en-v1.5`) | Avoid API embedding costs and leverage Groq's high speed for LLM reasoning | Tasks 12, 16, 18, 26, 28, 29, 59 |

*Example entry:*
| 2026-08-02 | Switched equation extraction confidence threshold from 0.8 to 0.6 | LlamaParse under-flagged valid equations at 0.8, causing false low-confidence markers | Task 11 (`ingestion/segmenter.py`) |

---

## Known Issues / Tech Debt

*Things you knowingly deferred. Not bugs you're hiding — bugs you've triaged and decided are OK to leave for now.*

| Issue | Severity | Deferred to |
|---|---|---|
| | | |

---

## Session Start Checklist (for you, before opening Antigravity)

1. Read "Current Status" above — know what task you're resuming
2. Read the last 2-3 rows of Commit Log — know what just happened
3. Read any open items in Decisions Log / Known Issues that might affect today's task
4. Attach this file (`@HANDOFF.md`) plus the standard context files in your Antigravity prompt

## Session End Checklist (for you, before closing Antigravity)

1. Update "Current Status" — new last-completed task, new next-task
2. Add a row to Commit Log for each commit made this session
3. Add any new Decisions Log entries if you deviated from spec or made a judgment call
4. Add any new Known Issues you triaged but didn't fix
5. Commit this file itself — `docs: update HANDOFF.md [session end]`
