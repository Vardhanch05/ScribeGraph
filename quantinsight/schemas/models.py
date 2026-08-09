from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


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


class TableUnit(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    paper_id: UUID
    chunk_id: UUID
    caption: str | None = None
    headers: list[str]
    rows: list[list[str]]
    page_number: int

    @model_validator(mode="after")
    def validate_row_lengths(self) -> TableUnit:
        for row in self.rows:
            if len(row) != len(self.headers):
                raise ValueError(
                    "All rows in a TableUnit must match the length of the headers."
                )
        return self


class EquationUnit(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    paper_id: UUID
    chunk_id: UUID
    latex: str
    surrounding_context: str
    equation_label: str | None = None
    page_number: int


class Citation(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    paper_id: UUID
    cited_text: str
    cited_work_raw: str
    resolved_arxiv_id: str | None = None


class CitedSummary(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    paper_id: UUID
    summary: str
    key_claims: list[str]
    supporting_chunk_ids: list[UUID]
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    model_used: str


class AgentTraceStep(BaseModel):
    step_index: int
    node_name: str
    input_summary: str
    output_summary: str
    tool_calls: list[dict] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class QueryResponse(BaseModel):
    answer: str
    citations: list[UUID]
    trace: list[AgentTraceStep]
    self_correction_applied: bool
    confidence_note: str | None = None


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class ErrorResponse(BaseModel):
    error: ErrorDetail


class IngestResponse(BaseModel):
    paper_id: UUID
    status: str
    warnings: list[str] = Field(default_factory=list)


class PaperDetailResponse(BaseModel):
    paper: SourcePaper
    summary: CitedSummary | None = None


class QueryRequest(BaseModel):
    query: str
    paper_ids: list[UUID] = Field(default_factory=list)
