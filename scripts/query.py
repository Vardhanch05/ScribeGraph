import argparse
import asyncio
import os
import sys
from uuid import UUID

# Ensure quantinsight package is importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from quantinsight.agent.graph import run_agent
from quantinsight.schemas.models import PaperChunk, TableUnit, EquationUnit
from quantinsight.storage.sqlite_store import (
    get_chunk_by_id,
    get_equation_by_chunk_id,
    get_paper_by_id,
    get_table_by_chunk_id,
    init_db,
    list_all_papers,
)


def resolve_papers(paper_args: list[str]) -> list[UUID]:
    """
    Resolve paper UUIDs from user arguments (which can be UUID strings or arXiv IDs).
    """
    all_papers = list_all_papers()
    paper_map = {p.id: p for p in all_papers}
    arxiv_map = {p.arxiv_id: p for p in all_papers if p.arxiv_id}

    resolved_ids = []
    for arg in paper_args:
        # Check if it is a valid UUID
        try:
            val = UUID(arg)
            if val in paper_map:
                resolved_ids.append(val)
            else:
                print(f"Warning: Paper UUID '{arg}' not found in database. Skipping.")
        except ValueError:
            # Not a UUID, try to match by arXiv ID
            matched = arxiv_map.get(arg.strip())
            if matched:
                resolved_ids.append(matched.id)
            else:
                # Try partial title search
                title_matches = [
                    p for p in all_papers if arg.lower() in p.title.lower()
                ]
                if title_matches:
                    resolved_ids.append(title_matches[0].id)
                    print(
                        f"Resolved '{arg}' to paper '{title_matches[0].title}' by title match."
                    )
                else:
                    print(
                        f"Warning: Argument '{arg}' is neither a valid UUID nor an arXiv ID nor matches a paper title in the database. Skipping."
                    )

    return resolved_ids


async def main():
    init_db()
    parser = argparse.ArgumentParser(
        description="QuantInsight RAG Agent Query CLI"
    )
    parser.add_argument(
        "--question",
        "-q",
        type=str,
        required=True,
        help="The query/question to run through the agent loop",
    )
    parser.add_argument(
        "--paper-ids",
        "-p",
        type=str,
        nargs="*",
        default=[],
        help="UUIDs, arXiv IDs, or titles of papers to query. If omitted, queries all ingested papers.",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Enable mock LLM mode (sets MOCK_LLM=true environment variable)",
    )

    args = parser.parse_args()

    if args.mock:
        os.environ["MOCK_LLM"] = "true"
        print("Mock LLM mode enabled.")

    # 1. Resolve Paper UUIDs
    all_papers = list_all_papers()
    if not all_papers:
        print("ERROR: No papers found in the database. Please ingest some papers first using scripts/ingest.py.")
        sys.exit(1)

    if args.paper_ids:
        resolved_uuids = resolve_papers(args.paper_ids)
        if not resolved_uuids:
            print("ERROR: None of the specified papers could be resolved.")
            sys.exit(1)
    else:
        resolved_uuids = [p.id for p in all_papers]
        print(f"No specific papers provided. Querying across all {len(resolved_uuids)} ingested papers.")

    print("\nQuerying papers:")
    for pid in resolved_uuids:
        p = get_paper_by_id(pid)
        if p:
            print(f"  - [{p.arxiv_id or 'N/A'}] {p.title} (UUID: {p.id})")

    print(f"\nQuestion: '{args.question}'")
    print("Running LangGraph agent loop...")

    try:
        response = await run_agent(args.question, paper_ids=resolved_uuids)
    except Exception as e:
        print(f"\nAgent execution failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    print("\n" + "=" * 80)
    print("AGENT RESPONSE SUMMARY")
    print("=" * 80)
    print(f"Answer:\n{response.answer}")
    print("\nSelf-Correction Applied: " + ("Yes" if response.self_correction_applied else "No"))
    if response.confidence_note:
        print(f"Confidence Note:          {response.confidence_note}")

    print("\nCitations:")
    if not response.citations:
        print("  No citations.")
    else:
        for idx, cid in enumerate(response.citations, 1):
            # Try finding chunk
            chunk = get_chunk_by_id(cid)
            if chunk:
                paper = get_paper_by_id(chunk.paper_id)
                paper_title = paper.title if paper else "Unknown Paper"
                paper_arxiv = paper.arxiv_id if paper else "Unknown ArXiv"
                print(f"  [{idx}] Chunk ID: {cid}")
                print(f"      Paper: [{paper_arxiv}] {paper_title}")
                print(f"      Type: {chunk.chunk_type.value.upper()} | Page: {chunk.page_number}")
                if chunk.section_title:
                    print(f"      Section: {chunk.section_title}")
                snippet = chunk.content.replace("\n", " ")
                if len(snippet) > 200:
                    snippet = snippet[:200] + "..."
                print(f"      Snippet: {snippet}")
            else:
                # Check table
                table = get_table_by_chunk_id(cid)
                if table:
                    paper = get_paper_by_id(table.paper_id)
                    paper_title = paper.title if paper else "Unknown Paper"
                    print(f"  [{idx}] Chunk ID: {cid} (TABLE)")
                    print(f"      Paper: {paper_title}")
                    print(f"      Page: {table.page_number} | Caption: {table.caption or 'None'}")
                else:
                    # Check equation
                    eq = get_equation_by_chunk_id(cid)
                    if eq:
                        paper = get_paper_by_id(eq.paper_id)
                        paper_title = paper.title if paper else "Unknown Paper"
                        print(f"  [{idx}] Chunk ID: {cid} (EQUATION)")
                        print(f"      Paper: {paper_title}")
                        print(f"      Page: {eq.page_number} | LaTeX: {eq.latex}")
                    else:
                        print(f"  [{idx}] Chunk ID: {cid} (Metadata not found in SQLite)")
            print()

    print("=" * 80)
    print("AGENT EXECUTION TRACE STEPS")
    print("=" * 80)
    for step in response.trace:
        print(f"Step {step.step_index + 1}: {step.node_name}")
        print(f"  Input Summary:  {step.input_summary}")
        print(f"  Output Summary: {step.output_summary}")
        if step.tool_calls:
            print(f"  Tool Calls:     {step.tool_calls}")
        print(f"  Timestamp:      {step.timestamp}")
        print("-" * 50)


if __name__ == "__main__":
    if sys.platform.startswith("win"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
            sys.stderr.reconfigure(encoding="utf-8")
        except AttributeError:
            pass
    asyncio.run(main())
