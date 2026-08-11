import logging
import os
from uuid import UUID

import chromadb
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from quantinsight.schemas.models import ChunkType, EquationUnit, PaperChunk, TableUnit

WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
CHROMA_DIR = os.path.join(WORKSPACE_ROOT, "data", "chroma")

logger = logging.getLogger(__name__)

_model = None


def get_embedding_model():
    """Lazy loader for SentenceTransformer model."""
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer

        _model = SentenceTransformer("BAAI/bge-small-en-v1.5")
    return _model


def get_chroma_client() -> chromadb.PersistentClient:
    """Initialize persistent ChromaDB client."""
    os.makedirs(CHROMA_DIR, exist_ok=True)
    return chromadb.PersistentClient(path=CHROMA_DIR)


def get_collection(client: chromadb.PersistentClient, name: str) -> chromadb.Collection:
    """Get or create a ChromaDB collection."""
    return client.get_or_create_collection(name=name)


import asyncio


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.5, min=1, max=5),
    retry=retry_if_exception_type(Exception),
    reraise=True,
)
async def delete_paper_embeddings(paper_id: UUID) -> None:
    """Delete all embeddings related to the given paper_id across all collections."""

    def _delete():
        client = get_chroma_client()
        collections = ["prose_chunks", "table_chunks", "equation_chunks"]
        for col_name in collections:
            try:
                coll = client.get_collection(col_name)
                # Delete entries matching metadata filter for paper_id
                coll.delete(where={"paper_id": str(paper_id)})
            except ValueError:
                # Collection does not exist yet, skip
                pass
            except Exception as e:
                logger.error(f"Error deleting embeddings from {col_name}: {e}")
                raise

    await asyncio.to_thread(_delete)


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.5, min=1, max=5),
    retry=retry_if_exception_type(Exception),
    reraise=True,
)
async def save_embeddings(
    chunks: list[PaperChunk], tables: list[TableUnit], equations: list[EquationUnit]
) -> None:
    """
    Generate embeddings and save chunks, tables, and equations to ChromaDB.
    Updates the embedding_id on each PaperChunk.
    """
    if not chunks:
        return

    def _save():
        client = get_chroma_client()
        model = get_embedding_model()

        prose_coll = get_collection(client, "prose_chunks")
        table_coll = get_collection(client, "table_chunks")
        equation_coll = get_collection(client, "equation_chunks")

        # Map chunks for quick lookup by chunk_id
        chunk_map = {c.id: c for c in chunks}

        # 1. Process Prose / Figure Caption Chunks
        prose_chunks_list = [
            c
            for c in chunks
            if c.chunk_type in (ChunkType.PROSE, ChunkType.FIGURE_CAPTION)
        ]
        if prose_chunks_list:
            texts = [c.content for c in prose_chunks_list]
            embeddings = model.encode(texts).tolist()

            ids = [str(c.id) for c in prose_chunks_list]
            metadatas = [
                {"paper_id": str(c.paper_id), "page_number": c.page_number}
                for c in prose_chunks_list
            ]

            prose_coll.add(
                ids=ids, embeddings=embeddings, metadatas=metadatas, documents=texts
            )
            for c in prose_chunks_list:
                c.embedding_id = str(c.id)

        # 2. Process Table Units
        if tables:
            texts = [
                f"Table caption: {t.caption or ''}. Headers: {', '.join(t.headers)}."
                for t in tables
            ]
            embeddings = model.encode(texts).tolist()

            ids = [str(t.chunk_id) for t in tables]
            metadatas = [
                {"paper_id": str(t.paper_id), "page_number": t.page_number}
                for t in tables
            ]

            table_coll.add(
                ids=ids, embeddings=embeddings, metadatas=metadatas, documents=texts
            )
            # Update corresponding chunk's embedding_id
            for t in tables:
                if t.chunk_id in chunk_map:
                    chunk_map[t.chunk_id].embedding_id = str(t.chunk_id)

        # 3. Process Equation Units
        if equations:
            texts = [
                f"Equation: {eq.latex}. Context: {eq.surrounding_context}"
                for eq in equations
            ]
            embeddings = model.encode(texts).tolist()

            ids = [str(eq.chunk_id) for eq in equations]
            metadatas = [
                {"paper_id": str(eq.paper_id), "page_number": eq.page_number}
                for eq in equations
            ]

            equation_coll.add(
                ids=ids, embeddings=embeddings, metadatas=metadatas, documents=texts
            )
            # Update corresponding chunk's embedding_id
            for eq in equations:
                if eq.chunk_id in chunk_map:
                    chunk_map[eq.chunk_id].embedding_id = str(eq.chunk_id)

    await asyncio.to_thread(_save)


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.5, min=1, max=5),
    retry=retry_if_exception_type(Exception),
    reraise=True,
)
async def search(
    query: str,
    paper_ids: list[UUID] | None = None,
    chunk_types: list[ChunkType] | None = None,
    limit: int = 5,
) -> list[PaperChunk | TableUnit | EquationUnit]:
    """
    Search ChromaDB collections and retrieve the original structured objects from SQLite.

    Routes queries to the appropriate collections based on chunk_types.
    If chunk_types is empty/None, searches all collections.
    """
    if paper_ids is not None and not paper_ids:
        return []


    from quantinsight.storage.sqlite_store import (
        get_chunk_by_id,
        get_equation_by_chunk_id,
        get_table_by_chunk_id,
    )

    def _search() -> list[tuple[str, UUID, float]]:
        client = get_chroma_client()
        model = get_embedding_model()
        query_vector = model.encode(query).tolist()

        # 1. Determine collections to query
        collections_to_search = set()
        if not chunk_types:
            collections_to_search = {"prose_chunks", "table_chunks", "equation_chunks"}
        else:
            for ct in chunk_types:
                if ct in (ChunkType.PROSE, ChunkType.FIGURE_CAPTION):
                    collections_to_search.add("prose_chunks")
                elif ct == ChunkType.TABLE:
                    collections_to_search.add("table_chunks")
                elif ct == ChunkType.EQUATION:
                    collections_to_search.add("equation_chunks")

        # 2. Build ChromaDB metadata filter
        where_filter = None
        if paper_ids:
            if len(paper_ids) == 1:
                where_filter = {"paper_id": str(paper_ids[0])}
            else:
                where_filter = {"paper_id": {"$in": [str(pid) for pid in paper_ids]}}

        # 3. Query target collections
        raw_results = []
        for col_name in collections_to_search:
            try:
                coll = client.get_collection(col_name)
                results = coll.query(
                    query_embeddings=[query_vector],
                    n_results=limit,
                    where=where_filter,
                )
                if results and "ids" in results and results["ids"]:
                    ids = results["ids"][0]
                    distances = (
                        results["distances"][0]
                        if results.get("distances")
                        else [0.0] * len(ids)
                    )
                    for doc_id, dist in zip(ids, distances):
                        raw_results.append((col_name, UUID(doc_id), dist))
            except ValueError:
                # Collection does not exist yet, skip
                continue

        # 4. Sort all results by distance (ascending) and take top limit
        raw_results.sort(key=lambda x: x[2])
        return raw_results[:limit]

    # Run ChromaDB retrieval in thread pool
    raw_results = await asyncio.to_thread(_search)

    # 5. Resolve SQLite objects for the top matches
    resolved_elements = []
    for col_name, item_id, _dist in raw_results:
        if col_name == "prose_chunks":
            chunk = get_chunk_by_id(item_id)
            if chunk:
                resolved_elements.append(chunk)
        elif col_name == "table_chunks":
            table = get_table_by_chunk_id(item_id)
            if table:
                resolved_elements.append(table)
        elif col_name == "equation_chunks":
            eq = get_equation_by_chunk_id(item_id)
            if eq:
                resolved_elements.append(eq)

    return resolved_elements
