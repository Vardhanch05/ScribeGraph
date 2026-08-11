# ScribeGraph Model Context Protocol (MCP) Server

ScribeGraph features a built-in MCP server implemented using `FastMCP`. This exposes ScribeGraph's vector retrieval, structured paper summaries, LaTeX equation lookup, and self-correcting agentic QA capabilities directly to MCP-compliant AI assistants like Claude Desktop, Cursor, and Windsurf.

---

## Tool Schemas

### 1. `search_papers`
Performs type-aware hybrid retrieval across prose, table, and equation vector collections.

- **Parameters:**
  - `query` (`string`, required): Semantic query text.
  - `paper_ids` (`array[string]`, optional): List of paper UUID strings to restrict search scope.
- **Returns:** List of matching `PaperChunk`, `TableUnit`, or `EquationUnit` structured objects.

### 2. `get_paper_summary`
Retrieves the pre-generated `CitedSummary` for a specific paper.

- **Parameters:**
  - `paper_id` (`string`, required): Target paper UUID string.
- **Returns:** `CitedSummary` object containing high-level summary, key claims, supporting chunk IDs, and LLM model metadata.

### 3. `get_equation_context`
Searches LaTeX equations and surrounding text context.

- **Parameters:**
  - `paper_id` (`string`, required): Target paper UUID string.
  - `equation_label` (`string`, optional): Equation label substring (e.g., `"eq. 1"`, `"1"`).
- **Returns:** List of matching `EquationUnit` objects with raw LaTeX formulas and surrounding prose.

### 4. `ask_quantinsight`
Runs the complete multi-node ScribeGraph agent loop (Planner → Retriever → Synthesizer → Verifier) over the paper collection.

- **Parameters:**
  - `query` (`string`, required): Question for the ScribeGraph reasoning agent.
  - `paper_ids` (`array[string]`, optional): List of paper UUID strings to scope the query.
- **Returns:** `QueryResponse` object containing `answer`, `citations`, `trace`, and `self_correction_applied` flag.

---

## Client Integration Guide

### Claude Desktop Setup

Add the following block to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "scribegraph": {
      "command": "uv",
      "args": [
        "--directory",
        "D:/personal/projects/QuantInsight",
        "run",
        "python",
        "-m",
        "quantinsight.mcp_server.server"
      ]
    }
  }
}
```
