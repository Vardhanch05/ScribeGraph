import os
import logging
from uuid import UUID
from typing import List, Optional
import chromadb
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from quantinsight.schemas.models import PaperChunk, TableUnit, EquationUnit, ChunkType

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

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.5, min=1, max=5),
    retry=retry_if_exception_type(Exception),
    reraise=True
)
def delete_paper_embeddings(paper_id: UUID) -> None:
    """Delete all embeddings related to the given paper_id across all collections."""
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

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.5, min=1, max=5),
    retry=retry_if_exception_type(Exception),
    reraise=True
)
def save_embeddings(
    chunks: List[PaperChunk],
    tables: List[TableUnit],
    equations: List[EquationUnit]
) -> None:
    """
    Generate embeddings and save chunks, tables, and equations to ChromaDB.
    Updates the embedding_id on each PaperChunk.
    """
    if not chunks:
        return

    client = get_chroma_client()
    model = get_embedding_model()

    prose_coll = get_collection(client, "prose_chunks")
    table_coll = get_collection(client, "table_chunks")
    equation_coll = get_collection(client, "equation_chunks")

    # Map chunks for quick lookup by chunk_id
    chunk_map = {c.id: c for c in chunks}
    
    # 1. Process Prose / Figure Caption Chunks
    prose_chunks_list = [c for c in chunks if c.chunk_type in (ChunkType.PROSE, ChunkType.FIGURE_CAPTION)]
    if prose_chunks_list:
        texts = [c.content for c in prose_chunks_list]
        embeddings = model.encode(texts).tolist()
        
        ids = [str(c.id) for c in prose_chunks_list]
        metadatas = [{"paper_id": str(c.paper_id), "page_number": c.page_number} for c in prose_chunks_list]
        
        prose_coll.add(
            ids=ids,
            embeddings=embeddings,
            metadatas=metadatas,
            documents=texts
        )
        for c in prose_chunks_list:
            c.embedding_id = str(c.id)

    # 2. Process Table Units
    if tables:
        texts = [f"Table caption: {t.caption or ''}. Headers: {', '.join(t.headers)}." for t in tables]
        embeddings = model.encode(texts).tolist()
        
        ids = [str(t.chunk_id) for t in tables]
        metadatas = [{"paper_id": str(t.paper_id), "page_number": t.page_number} for t in tables]
        
        table_coll.add(
            ids=ids,
            embeddings=embeddings,
            metadatas=metadatas,
            documents=texts
        )
        # Update corresponding chunk's embedding_id
        for t in tables:
            if t.chunk_id in chunk_map:
                chunk_map[t.chunk_id].embedding_id = str(t.chunk_id)

    # 3. Process Equation Units
    if equations:
        texts = [f"Equation: {eq.latex}. Context: {eq.surrounding_context}" for eq in equations]
        embeddings = model.encode(texts).tolist()
        
        ids = [str(eq.chunk_id) for eq in equations]
        metadatas = [{"paper_id": str(eq.paper_id), "page_number": eq.page_number} for eq in equations]
        
        equation_coll.add(
            ids=ids,
            embeddings=embeddings,
            metadatas=metadatas,
            documents=texts
        )
        # Update corresponding chunk's embedding_id
        for eq in equations:
            if eq.chunk_id in chunk_map:
                chunk_map[eq.chunk_id].embedding_id = str(eq.chunk_id)
