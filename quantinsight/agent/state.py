from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field

from quantinsight.schemas.models import (
    AgentTraceStep,
    EquationUnit,
    PaperChunk,
    QueryResponse,
    TableUnit,
)


class GraphState(BaseModel):
    query: str
    paper_ids: list[UUID] = Field(default_factory=list)

    plan: str | None = None
    retrieved_chunks: list[PaperChunk] = Field(default_factory=list)
    retrieved_tables: list[TableUnit] = Field(default_factory=list)
    retrieved_equations: list[EquationUnit] = Field(default_factory=list)
    draft_answer: str | None = None
    verification_notes: list[str] = Field(default_factory=list)
    needs_revision: bool = False
    revision_count: int = 0  # enforces CP-7 max-2 loop cap
    final_answer: QueryResponse | None = None
    trace: list[AgentTraceStep] = Field(default_factory=list)
