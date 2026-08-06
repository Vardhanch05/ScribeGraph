import argparse
import asyncio
import os
import sys
from uuid import UUID

# Ensure quantinsight package is importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from quantinsight.schemas.models import ChunkType, PaperChunk, TableUnit, EquationUnit
from quantinsight.storage.chroma_store import search
from quantinsight.storage.sqlite_store import list_all_papers

# Spot check queries to run by default
DEFAULT_QUERIES = [
    {
        "query": "multi-head relational attention topologies",
        "paper_arxiv_id": "1706.03762",  # Attention Is All You Need
        "chunk_types": [ChunkType.PROSE],
        "description": "Semantic query for prose content in the Attention paper",
    },
    {
        "query": "Attention(Q, K, V) = softmax",
        "paper_arxiv_id": "1706.03762",
        "chunk_types": [ChunkType.EQUATION],
        "description": "Specific equation search in the Attention paper",
    },
    {
        "query": "Maximum path lengths, per-layer complexity",
        "paper_arxiv_id": "1706.03762",
        "chunk_types": [ChunkType.TABLE],
        "description": "Table lookup for path lengths and complexity in the Attention paper",
    },
    {
        "query": "degradation problem in deep neural networks",
        "paper_arxiv_id": "1512.03385",  # ResNet
        "chunk_types": [ChunkType.PROSE],
        "description": "Prose query on ResNet degradation problem",
    },
    {
        "query": "error rates for ResNet on ImageNet",
        "paper_arxiv_id": "1512.03385",
        "chunk_types": [ChunkType.TABLE],
        "description": "Table search for ResNet error rates",
    },
    {
        "query": "initialization bias correction derivation",
        "paper_arxiv_id": "1412.6980",  # Adam
        "chunk_types": [ChunkType.PROSE],
        "description": "Prose query on Adam bias correction derivation",
    },
    {
        "query": "Adam hyper-parameters default settings",
        "paper_arxiv_id": "1412.6980",
        "chunk_types": [ChunkType.PROSE],
        "description": "Prose query for default hyperparameter settings in Adam",
    },
]


async def run_spot_check():
    parser = argparse.ArgumentParser(
        description="QuantInsight Retrieval Manual Relevance Spot-Check Script"
    )
    parser.add_argument(
        "--query",
        type=str,
        help="Custom search query (bypasses default test queries if provided)",
    )
    parser.add_argument(
        "--paper-id",
        type=str,
        help="Filter custom query to a specific paper UUID",
    )
    parser.add_argument(
        "--type",
        type=str,
        choices=["prose", "table", "equation"],
        help="Filter custom query to a specific chunk type",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=3,
        help="Maximum results to return per query",
    )

    args = parser.parse_args()

    # Load all ingested papers for mapping paper_id -> metadata
    papers = list_all_papers()
    paper_map = {p.id: p for p in papers}
    arxiv_map = {p.arxiv_id: p for p in papers if p.arxiv_id}

    if not papers:
        print("ERROR: No papers found in the database. Please ingest some papers first.")
        sys.exit(1)

    print("=" * 80)
    print(f"QUANTINSIGHT SPOT-CHECK (Found {len(papers)} ingested papers)")
    for p in papers:
        print(f"  - [{p.arxiv_id}] {p.title} (ID: {p.id})")
    print("=" * 80)

    if args.query:
        # Run single custom query
        paper_ids = [UUID(args.paper_id)] if args.paper_id else None
        chunk_types = [ChunkType(args.type)] if args.type else None
        queries_to_run = [
            {
                "query": args.query,
                "paper_ids": paper_ids,
                "chunk_types": chunk_types,
                "description": "Custom user query",
            }
        ]
    else:
        # Map default test queries to their UUIDs in this database instance
        queries_to_run = []
        for dq in DEFAULT_QUERIES:
            paper = arxiv_map.get(dq["paper_arxiv_id"])
            if not paper:
                print(
                    f"Warning: ArXiv paper {dq['paper_arxiv_id']} not found in DB. Skipping query."
                )
                continue
            queries_to_run.append(
                {
                    "query": dq["query"],
                    "paper_ids": [paper.id],
                    "chunk_types": dq["chunk_types"],
                    "description": dq["description"],
                }
            )

    for i, q in enumerate(queries_to_run, 1):
        print(f"\nQUERY #{i}: '{q['query']}'")
        print(f"Description: {q['description']}")
        print(f"Filters: paper_ids={q.get('paper_ids')}, chunk_types={q.get('chunk_types')}")
        print("-" * 80)

        results = await search(
            query=q["query"],
            paper_ids=q.get("paper_ids"),
            chunk_types=q.get("chunk_types"),
            limit=args.limit,
        )

        if not results:
            print("  --> No results returned.")
            continue

        for idx, item in enumerate(results, 1):
            paper_info = paper_map.get(item.paper_id)
            paper_title = paper_info.title if paper_info else "Unknown"
            paper_arxiv = paper_info.arxiv_id if paper_info else "Unknown"

            if isinstance(item, PaperChunk):
                print(f"  [{idx}] Type: PROSE/CAPTION | Paper: [{paper_arxiv}] {paper_title} | Page: {item.page_number}")
                if item.section_title:
                    print(f"      Section: {item.section_title}")
                snippet = item.content.replace('\n', ' ')
                if len(snippet) > 250:
                    snippet = snippet[:250] + "..."
                print(f"      Content: {snippet}")

            elif isinstance(item, TableUnit):
                print(f"  [{idx}] Type: TABLE | Paper: [{paper_arxiv}] {paper_title} | Page: {item.page_number}")
                if item.caption:
                    print(f"      Caption: {item.caption}")
                print(f"      Headers: {', '.join(item.headers)}")
                # Show first 3 rows
                row_str = " | ".join([", ".join(r) for r in item.rows[:3]])
                if len(item.rows) > 3:
                    row_str += " ... (+ more rows)"
                print(f"      Rows: {row_str}")

            elif isinstance(item, EquationUnit):
                print(f"  [{idx}] Type: EQUATION | Paper: [{paper_arxiv}] {paper_title} | Page: {item.page_number}")
                print(f"      LaTeX: {item.latex}")
                context_snippet = item.surrounding_context.replace('\n', ' ')
                if len(context_snippet) > 200:
                    context_snippet = context_snippet[:200] + "..."
                print(f"      Surrounding Context: {context_snippet}")
            print()


if __name__ == "__main__":
    if sys.platform.startswith("win"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
            sys.stderr.reconfigure(encoding="utf-8")
        except AttributeError:
            pass
    asyncio.run(run_spot_check())
