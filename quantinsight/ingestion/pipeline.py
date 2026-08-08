import logging
import os
import uuid
from datetime import UTC, datetime
from uuid import UUID, uuid4

from quantinsight.ingestion.parser import parse_pdf
from quantinsight.ingestion.segmenter import segment_markdown
from quantinsight.ingestion.summary import generate_cited_summary
from quantinsight.schemas.models import (
    Citation,
    SourcePaper,
)
from quantinsight.storage.chroma_store import delete_paper_embeddings, save_embeddings
from quantinsight.storage.sqlite_store import (
    clean_paper_child_records,
    get_paper_by_arxiv_id,
    init_db,
    save_paper_elements,
    save_paper_metadata,
)

logger = logging.getLogger(__name__)


async def ingest_paper(
    arxiv_id: str | None = None,
    pdf_bytes: bytes | None = None,
    title: str | None = None,
    authors: list[str] | None = None,
    api_key: str | None = None,
    groq_api_key: str | None = None,
    model: str = "llama-3.3-70b-versatile",
) -> tuple[UUID, list[str]]:
    """
    Orchestrate the ingestion pipeline:
    1. Parse PDF (LlamaParse) to get raw markdown
    2. Segment markdown to chunks, tables, equations
    3. Perform idempotent check & setup paper ID
    4. Generate CitedSummary
    5. Generate embeddings and save to ChromaDB
    6. Save to SQLite database

    Returns:
        Tuple of (paper_id, warnings)
    """
    # Initialize SQLite database schema
    init_db()

    # 1. Parse PDF or fetch from arXiv
    existing_paper = None
    if arxiv_id:
        existing_paper = get_paper_by_arxiv_id(arxiv_id)

    paper_id = existing_paper.id if existing_paper else uuid4()

    # Run parsing wrapper
    raw_markdown = await parse_pdf(
        arxiv_id=arxiv_id, pdf_bytes=pdf_bytes, paper_id=paper_id, api_key=api_key
    )

    # 2. Segment markdown
    chunks, tables, equations, warnings = segment_markdown(raw_markdown, paper_id)

    # 3. Apply stable, deterministic UUIDs for consistency on re-ingest
    id_mapping = {}
    for chunk in chunks:
        old_id = chunk.id
        new_id = uuid.uuid5(paper_id, f"chunk_{chunk.order_index}")
        chunk.id = new_id
        chunk.paper_id = paper_id
        id_mapping[old_id] = new_id

    for t in tables:
        t.paper_id = paper_id
        t.chunk_id = id_mapping[t.chunk_id]
        t.id = uuid.uuid5(paper_id, f"table_{t.chunk_id}")

    for eq in equations:
        eq.paper_id = paper_id
        eq.chunk_id = id_mapping[eq.chunk_id]
        eq.id = uuid.uuid5(paper_id, f"equation_{eq.chunk_id}")

    # 4. If this is a re-ingestion, clean up old child database records & embeddings
    if existing_paper:
        logger.info(
            f"Re-ingesting paper {arxiv_id}. Cleaning old child records and embeddings..."
        )
        clean_paper_child_records(paper_id)
        await delete_paper_embeddings(paper_id)

    # 5. Generate CitedSummary using Groq LLM
    summary = await generate_cited_summary(
        paper_id=paper_id, chunks=chunks, api_key=groq_api_key, model=model
    )

    # 6. Generate embeddings and save to ChromaDB (updates chunk.embedding_id in place)
    await save_embeddings(chunks, tables, equations)

    # 7. Create/Update SourcePaper metadata
    page_count = max([c.page_number for c in chunks]) if chunks else 1
    resolved_title = title or (
        existing_paper.title if existing_paper else f"Paper {arxiv_id or paper_id}"
    )
    resolved_authors = authors or (
        existing_paper.authors if existing_paper else ["Unknown"]
    )

    from quantinsight.ingestion.parser import ARTIFACTS_DIR

    raw_markdown_path = os.path.join(ARTIFACTS_DIR, str(paper_id), "raw.md")

    paper = SourcePaper(
        id=paper_id,
        arxiv_id=arxiv_id,
        title=resolved_title,
        authors=resolved_authors,
        source_url=f"https://arxiv.org/abs/{arxiv_id}" if arxiv_id else None,
        ingested_at=datetime.now(UTC),
        raw_markdown_path=raw_markdown_path,
        page_count=page_count,
    )

    # 8. Save metadata and child items in SQLite
    save_paper_metadata(paper)

    # Citations are empty for now as they're not extracted in Phase 1
    citations: list[Citation] = []

    save_paper_elements(chunks, tables, equations, citations, summary)

    logger.info(f"Ingestion pipeline completed successfully for paper {paper_id}")
    return paper_id, warnings
