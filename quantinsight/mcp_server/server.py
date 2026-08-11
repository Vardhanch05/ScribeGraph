from uuid import UUID
from mcp.server.fastmcp import FastMCP

from quantinsight.agent.graph import run_agent
from quantinsight.storage.chroma_store import search
from quantinsight.storage.sqlite_store import (
    get_equations_by_paper,
    get_paper_summary as fetch_paper_summary,
)

mcp = FastMCP("ScribeGraph MCP Server")



@mcp.tool()
async def search_papers(query: str, paper_ids: list[str] | None = None) -> list[dict]:
    """
    Search across prose, table, and equation collections for relevant paper chunks.
    
    Args:
        query: Semantic query text
        paper_ids: Optional list of paper UUID strings to restrict search scope
    """
    parsed_ids = [UUID(pid) for pid in paper_ids] if paper_ids else None
    results = await search(query=query, paper_ids=parsed_ids)
    
    formatted_results = []
    for item in results:
        if hasattr(item, "model_dump"):
            formatted_results.append(item.model_dump(mode="json"))
        else:
            formatted_results.append(str(item))
    return formatted_results


@mcp.tool()
async def get_paper_summary(paper_id: str) -> dict:
    """
    Retrieve the structured CitedSummary for a given paper by its UUID string.
    
    Args:
        paper_id: Paper UUID string
    """
    summary = fetch_paper_summary(UUID(paper_id))
    if not summary:
        return {"error": f"No summary found for paper_id {paper_id}"}
    return summary.model_dump(mode="json")


@mcp.tool()
async def get_equation_context(paper_id: str, equation_label: str | None = None) -> list[dict]:
    """
    Look up equation units and LaTeX representations for a given paper.
    
    Args:
        paper_id: Paper UUID string
        equation_label: Optional label (e.g. 'eq. 1', '(1)') to filter
    """
    equations = get_equations_by_paper(UUID(paper_id))
    if equation_label:
        filtered = [
            eq for eq in equations
            if eq.equation_label and equation_label.lower() in eq.equation_label.lower()
        ]
        if filtered:
            equations = filtered

    return [eq.model_dump(mode="json") for eq in equations]


@mcp.tool()
async def ask_quantinsight(query: str, paper_ids: list[str] | None = None) -> dict:
    """
    Ask a question and receive a self-correcting agentic response with full citations.
    
    Args:
        query: Question to ask the ScribeGraph agent
        paper_ids: Optional list of paper UUID strings
    """
    parsed_ids = [UUID(pid) for pid in paper_ids] if paper_ids else []
    response = await run_agent(query=query, paper_ids=parsed_ids)
    return response.model_dump(mode="json")


if __name__ == "__main__":
    mcp.run()
