import logging
import re
from typing import Any
from uuid import UUID

from rank_bm25 import BM25Okapi
from sqlmodel import Session, select

from quantinsight.schemas.models import ChunkType, EquationUnit, PaperChunk, TableUnit
from quantinsight.storage.chroma_store import search as dense_search
from quantinsight.storage.sqlite_store import (
    EquationUnitDb,
    PaperChunkDb,
    TableUnitDb,
    engine,
    get_chunk_by_id,
    get_equation_by_chunk_id,
    get_table_by_chunk_id,
)

logger = logging.getLogger(__name__)

# Global cache for in-memory BM25 index
_bm25_index: BM25Okapi | None = None
_bm25_items: list[tuple[UUID, str, str, str]] = []  # (id/chunk_id, item_type, paper_id_str, text_content)


def bm25_tokenize(text: str) -> list[str]:
    """Tokenize text preserving exact symbols, words, numbers, and math tags."""
    if not text:
        return []
    return re.findall(r"\w+|[^\w\s]", text.lower())


def build_bm25_index(force_rebuild: bool = False):
    """Build or retrieve the in-memory BM25 index over all SQLite chunks."""
    global _bm25_index, _bm25_items
    if _bm25_index is not None and not force_rebuild:
        return

    items: list[tuple[UUID, str, str, str]] = []
    tokenized_corpus: list[list[str]] = []

    with Session(engine) as session:
        # 1. Index Paper Chunks
        prose_chunks = session.exec(select(PaperChunkDb)).all()
        for chunk in prose_chunks:
            text = f"{chunk.section_title or ''} {chunk.content or ''}"
            tokens = bm25_tokenize(text)
            if tokens:
                items.append((chunk.id, "prose", str(chunk.paper_id), text))
                tokenized_corpus.append(tokens)

        # 2. Index Table Units
        table_units = session.exec(select(TableUnitDb)).all()
        for tbl in table_units:
            text = f"Table {tbl.caption or ''}. Headers: {tbl.headers or ''}. Rows: {tbl.rows or ''}"
            tokens = bm25_tokenize(text)
            if tokens:
                items.append((tbl.chunk_id, "table", str(tbl.paper_id), text))
                tokenized_corpus.append(tokens)

        # 3. Index Equation Units
        eq_units = session.exec(select(EquationUnitDb)).all()
        for eq in eq_units:
            text = f"Equation {eq.equation_label or ''}: {eq.latex or ''}. Context: {eq.surrounding_context or ''}"
            tokens = bm25_tokenize(text)
            if tokens:
                items.append((eq.chunk_id, "equation", str(eq.paper_id), text))
                tokenized_corpus.append(tokens)

    if tokenized_corpus:
        _bm25_index = BM25Okapi(tokenized_corpus)
        _bm25_items = items
        logger.info(f"Built BM25 index over {len(_bm25_items)} total document units.")
    else:
        _bm25_index = None
        _bm25_items = []


def search_bm25(
    query: str,
    paper_ids: list[UUID] | None = None,
    chunk_types: list[ChunkType] | None = None,
    limit: int = 15,
) -> list[tuple[UUID, str, float]]:
    """Execute sparse BM25 keyword search over indexed documents."""
    build_bm25_index()
    if _bm25_index is None or not _bm25_items:
        return []

    tokens = bm25_tokenize(query)
    if not tokens:
        return []

    scores = _bm25_index.get_scores(tokens)
    paper_ids_str = {str(pid) for pid in paper_ids} if paper_ids else None
    allowed_types = (
        {ct.value if hasattr(ct, "value") else str(ct) for ct in chunk_types}
        if chunk_types
        else None
    )

    results: list[tuple[UUID, str, float]] = []
    for idx, score in enumerate(scores):
        if score <= 0.0:
            continue
        item_id, item_type, paper_id_str, _ = _bm25_items[idx]
        if paper_ids_str and paper_id_str not in paper_ids_str:
            continue
        if allowed_types and item_type not in allowed_types:
            continue
        results.append((item_id, item_type, float(score)))

    results.sort(key=lambda x: x[2], reverse=True)
    return results[:limit]


async def hybrid_search(
    query: str,
    paper_ids: list[UUID] | None = None,
    chunk_types: list[ChunkType] | None = None,
    limit: int = 8,
) -> list[PaperChunk | TableUnit | EquationUnit]:
    """
    Perform Hybrid Search using Reciprocal Rank Fusion (RRF) between:
    1. Dense Vector Embeddings (ChromaDB - BAAI/bge-small-en-v1.5)
    2. Sparse Keyword Matching (BM25)
    """
    # 1. Execute Dense Vector Search
    dense_results = await dense_search(
        query=query,
        paper_ids=paper_ids,
        chunk_types=chunk_types,
        limit=limit * 2,
    )

    # 2. Execute Sparse BM25 Search
    bm25_results = search_bm25(
        query=query, paper_ids=paper_ids, chunk_types=chunk_types, limit=limit * 2
    )

    # 3. Reciprocal Rank Fusion (RRF) scoring map: id -> rrf_score
    rrf_scores: dict[UUID, float] = {}
    item_type_map: dict[UUID, str] = {}
    item_obj_map: dict[UUID, Any] = {}

    # Rank constant k=60
    k_const = 60.0

    # Score Dense results
    for rank, item in enumerate(dense_results, 1):
        item_id = item.id if hasattr(item, "id") and not isinstance(item, (TableUnit, EquationUnit)) else getattr(item, "chunk_id", getattr(item, "id"))
        item_obj_map[item_id] = item
        if isinstance(item, PaperChunk):
            item_type_map[item_id] = "prose"
        elif isinstance(item, TableUnit):
            item_type_map[item_id] = "table"
        elif isinstance(item, EquationUnit):
            item_type_map[item_id] = "equation"
        rrf_scores[item_id] = rrf_scores.get(item_id, 0.0) + (1.0 / (k_const + rank))

    # Score BM25 results
    for rank, (item_id, item_type, _) in enumerate(bm25_results, 1):
        item_type_map[item_id] = item_type
        rrf_scores[item_id] = rrf_scores.get(item_id, 0.0) + (1.0 / (k_const + rank))

    # Sort items by final RRF score descending
    sorted_ids = sorted(rrf_scores.keys(), key=lambda uid: rrf_scores[uid], reverse=True)[:limit]

    # Resolve structured objects from SQLite for any BM25 hits not already in dense map
    final_items: list[PaperChunk | TableUnit | EquationUnit] = []
    for item_id in sorted_ids:
        if item_id in item_obj_map:
            final_items.append(item_obj_map[item_id])
        else:
            itype = item_type_map.get(item_id, "prose")
            if itype == "prose":
                obj = get_chunk_by_id(item_id)
            elif itype == "table":
                obj = get_table_by_chunk_id(item_id)
            elif itype == "equation":
                obj = get_equation_by_chunk_id(item_id)
            else:
                obj = None

            if obj:
                final_items.append(obj)

    return final_items


def get_parent_prose_chunks(paper_id: UUID, page_number: int, limit: int = 2) -> list[PaperChunk]:
    """Retrieve parent/surrounding prose chunks for a specific paper and page number."""
    with Session(engine) as session:
        db_chunks = session.exec(
            select(PaperChunkDb)
            .where(PaperChunkDb.paper_id == paper_id)
            .where(PaperChunkDb.page_number == page_number)
            .limit(limit)
        ).all()
        return [
            PaperChunk(
                id=c.id,
                paper_id=c.paper_id,
                chunk_type=ChunkType(c.chunk_type),
                content=c.content,
                page_number=c.page_number,
                section_title=c.section_title,
                order_index=c.order_index,
                embedding_id=c.embedding_id,
            )
            for c in db_chunks
        ]
