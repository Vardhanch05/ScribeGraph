# 21-Day Commit Schedule — ScribeGraph

Goal: 3 commits/day, 7 days/week, 21 days straight = **63 commits**, matching the 63 tasks in `.kiro/specs/quantinsight-core/tasks.md` 1:1. Each day's three commits = one meaningful, working, testable unit of progress — not padding.

## How to work each day in Kiro / Antigravity

1. **Before opening Antigravity:** read `HANDOFF.md` — "Current Status" tells you exactly where you left off, the Commit Log and Decisions Log tell you what happened and why.
2. Find today's 3 tasks in the table below.
3. In Antigravity, attach `@HANDOFF.md` along with the standard context files (`@.kiro/specs/quantinsight-core/tasks.md`, `@.kiro/specs/quantinsight-core/design.md`, `@AGENTS.md`) — this replaces reliance on the agent's own session memory, which may not persist.
4. Have Antigravity produce a plan artifact for the task, review it, approve, let it execute.
5. Review the diff. If it's right, commit immediately (don't batch — one task = one commit).
6. **Before closing Antigravity:** update `HANDOFF.md` (Current Status, Commit Log row, any Decisions/Known Issues) and commit that update too.
7. Repeat for tasks 2 and 3.

If a task runs long, it's fine to split it into a smaller real commit + a "WIP" continuation the next day — but try to keep each task genuinely shippable, since tasks were sized for this. If you stop mid-task, say so explicitly in `HANDOFF.md`'s "Blockers" field so tomorrow's session doesn't assume it's done.

## Commit message convention

Use Conventional Commits, referencing the task number and requirement ID for traceability:

```
<type>(<scope>): <short description> [task-N]

type: feat | fix | test | chore | docs | refactor
scope: schemas | ingestion | storage | agent | api | mcp | ui | eval | ci
```
Example: `feat(agent): implement Verifier node with needs_revision routing [task-29]`

---

## Schedule

| Day | Phase | Commit 1 (task #) | Commit 2 (task #) | Commit 3 (task #) |
|---|---|---|---|---|
| 1 | Setup | 1. Repo/uv/pyproject init | 2. Pre-commit + CI | 3. `.env.example` + scaffolding |
| 2 | Ingestion | 4. `SourcePaper`/`PaperChunk` schemas | 5. `TableUnit`/`EquationUnit` schemas | 6. `Citation`/`CitedSummary` schemas |
| 3 | Ingestion | 7. LlamaParse client wrapper | 8. Rate limiter | 9. Artifact persistence |
| 4 | Ingestion | 10. Segmentation logic | 11. Low-confidence flagging | 12. `CitedSummary` generation |
| 5 | Ingestion | 13. Idempotent re-ingestion | 14. Schema/segmentation unit tests | 15. `scripts/ingest.py` CLI + real-paper validation |
| 6 | Storage | 16. ChromaDB collections | 17. SQLite schema | 18. Embedding generation on ingest |
| 7 | Storage | 19. Type-aware `search()` | 20. Multi-paper query support | 21. Retrieval unit tests |
| 8 | Storage | 22. Ingest dev corpus (3–4 papers) | 23. Manual relevance spot-check script | 24. Retrieval tuning fixes |
| 9 | Agent | 25. `GraphState` schema | 26. Planner node | 27. Retriever node |
| 10 | Agent | 28. Synthesizer node (draft) | 29. Verifier node | 30. Conditional routing wiring |
| 11 | Agent | 31. Max-iteration guard + fallback | 32. LangGraph checkpointing | 33. `AgentTraceStep` logging contract |
| 12 | Agent | 34. "No evidence found" path | 35. Structured-output enforcement | 36. Agent graph tests (5 questions) |
| 13 | Agent | 37. Revision-loop test case | 38. `scripts/query.py` CLI + validation | 39. Prompt tuning + failure-mode docs |
| 14 | API | 40. FastAPI skeleton | 41. `/ingest` + status endpoints | 42. `/papers` endpoints |
| 15 | API | 43. `/query` endpoint | 44. `/query/stream` SSE + error middleware | 45. API tests (`TestClient`) |
| 16 | MCP | 46. `search_papers` + `get_paper_summary` tools | 47. `get_equation_context` + `ask_quantinsight` tools | 48. MCP client validation + README docs |
| 17 | UI | 49. Home / Paper Library page | 50. Ingest page + status/error UX | 51. Chat page skeleton |
| 18 | UI | 52. Wire Chat to in-process LangGraph streaming | 53. Equation/table rendering + revision badge | 54. Paper Explorer page |
| 19 | UI | 55. Eval Dashboard skeleton | 56. Full manual walkthrough + fixes | 57. Empty/loading/error state polish |
| 20 | Eval | 58. Build 15–30 question eval set | 59. `run_eval.py` + `/eval/run` wiring | 60. Baseline eval run + `results.md` |
| 21 | Eval | 61. Prompt/retrieval iteration + re-eval | 62. Final README pass | 63. Final CI pass + `v0.1` tag |

---

## Realism check — read this before you start

Three commits a day for 21 straight days is an aggressive but achievable *cadence commitment*, not a claim that every day will be equally hard. Some honest notes:

- **Days 9–13 (the agent phase) are the real crunch** — this is the highest-complexity, highest-uncertainty part of the whole project. If you fall behind here, it's the expected place to fall behind, not a sign you're doing something wrong. Consider front-loading slack by finishing Phase 1–2 (Days 1–8) a day or two early if they go smoothly.
- **A green streak isn't the actual goal — working software is.** If a day's task genuinely isn't done, commit an honest WIP with a clear message rather than a fake "complete" commit — a GitHub contribution graph with real, inspectable commits is worth more in an interview than a padded one, since interviewers sometimes do look at actual commit history and diffs, not just the graph.
- **Weekends are included in this 21-day count** (3 weeks straight, no rest days). If that's not realistic for you, an honest alternative is 3 commits/day on 15 weekdays across 3 calendar weeks (45 commits) — still a strong, consistent signal, just less punishing. Your call which version you actually commit to.
