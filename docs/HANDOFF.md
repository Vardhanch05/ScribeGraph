# HANDOFF.md — QuantInsight Session Log

**Purpose:** Antigravity's agent context may not persist between sessions. This file is the single source of truth for "where we left off" — read it at the start of every session, update it at the end of every session, before every commit round.

**Rule:** never start a new Antigravity session without attaching this file. Never end a session without updating it.

---

## Current Status

- **Day:** Day 1
- **Phase:** Phase 0 — Project Setup
- **Last completed task:** Task 1 — Initialize repo, `uv venv`, and `pyproject.toml`
- **Next task up:** Task 2 — Set up pre-commit config and GitHub Actions CI
- **Blockers / open questions:** None

---

## Commit Log

*Append one row per commit, in order. This is your ground truth — more reliable than trusting the agent's memory or Git log alone, since it also captures the "why," not just the diff.*

| Date | Task # | Commit hash (short) | Commit message | Notes |
|---|---|---|---|---|
| 2026-07-25 | 1 | (pending) | chore: initialize repo, uv venv, and pyproject.toml | Initialized project scaffolding, uv.lock, and .gitignore |

---

## Decisions Log

*Anything decided mid-build that isn't already in `docs/` or `.kiro/specs/` — deviations, tradeoffs, things you discovered. Keep entries short. If a decision is significant enough to affect future tasks, also update the relevant steering/spec file, don't just log it here and forget.*

| Date | Decision | Why | Affects |
|---|---|---|---|
| | | | |

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
