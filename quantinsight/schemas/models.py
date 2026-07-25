from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class ChunkType(str, Enum):
    PROSE = "prose"
    TABLE = "table"
    EQUATION = "equation"
    FIGURE_CAPTION = "figure_caption"


class SourcePaper(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    arxiv_id: str | None = None
    title: str
    authors: list[str]
    source_url: str | None = None
    ingested_at: datetime = Field(default_factory=datetime.utcnow)
    raw_markdown_path: str  # path to /artifacts/{paper_id}/raw.md
    page_count: int


class PaperChunk(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    paper_id: UUID
    chunk_type: ChunkType
    content: str
    page_number: int
    section_title: str | None = None
    order_index: int
    embedding_id: str | None = None  # pointer into ChromaDB
