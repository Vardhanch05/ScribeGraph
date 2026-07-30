import argparse
import asyncio
import logging
import os
import sys

# Ensure quantinsight package is importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from quantinsight.ingestion.pipeline import ingest_paper
from quantinsight.storage.sqlite_store import get_paper_by_id

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("ingest_cli")

async def main():
    parser = argparse.ArgumentParser(description="QuantInsight Ingestion Pipeline CLI")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--arxiv-id", type=str, help="arXiv ID to fetch and ingest (e.g. 2303.11111)")
    group.add_argument("--pdf-path", type=str, help="Path to local PDF file to parse and ingest")
    
    parser.add_argument("--title", type=str, help="Optional title of the paper (will fallback if not provided)")
    parser.add_argument("--authors", type=str, nargs="+", help="Optional author list (will fallback if not provided)")
    parser.add_argument("--model", type=str, default="llama-3.1-70b-versatile", help="Groq model name to use for CitedSummary generation")
    
    args = parser.parse_args()
    
    pdf_bytes = None
    if args.pdf_path:
        if not os.path.exists(args.pdf_path):
            logger.error(f"Local PDF file not found: {args.pdf_path}")
            sys.exit(1)
        with open(args.pdf_path, "rb") as f:  # noqa: ASYNC230
            pdf_bytes = f.read()
            
    print("Starting ingestion pipeline...")
    try:
        paper_id, warnings = await ingest_paper(
            arxiv_id=args.arxiv_id,
            pdf_bytes=pdf_bytes,
            title=args.title,
            authors=args.authors,
            model=args.model
        )
        
        # Retrieve final metadata from SQLite
        paper = get_paper_by_id(paper_id)
        
        print("\n" + "="*50)
        print("INGESTION SUMMARY")
        print("="*50)
        print("Status:      SUCCESS")
        print(f"Paper ID:    {paper_id}")
        if paper:
            print(f"Title:       {paper.title}")
            print(f"Authors:     {', '.join(paper.authors)}")
            print(f"ArXiv ID:    {paper.arxiv_id or 'N/A'}")
            print(f"Pages:       {paper.page_count}")
        print(f"Warnings:    {len(warnings)}")
        for idx, w in enumerate(warnings, 1):
            print(f"  {idx}. {w}")
        print("="*50 + "\n")
        
    except Exception:
        logger.exception("Ingestion failed")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
