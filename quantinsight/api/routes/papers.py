from uuid import UUID
from fastapi import APIRouter, HTTPException, status

from quantinsight.schemas.models import PaperDetailResponse, SourcePaper
from quantinsight.storage.sqlite_store import (
    get_paper_by_id,
    get_paper_summary,
    list_all_papers,
)

router = APIRouter(prefix="/papers", tags=["Papers"])


@router.get("", response_model=list[SourcePaper])
async def list_papers() -> list[SourcePaper]:
    """List all ingested papers."""
    return list_all_papers()


@router.get("/{paper_id}", response_model=PaperDetailResponse)
async def get_paper_detail(paper_id: UUID) -> PaperDetailResponse:
    """Retrieve detailed metadata and CitedSummary for a given paper."""
    paper = get_paper_by_id(paper_id)
    if not paper:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Paper with ID {paper_id} not found.",
        )
    summary = get_paper_summary(paper_id)
    return PaperDetailResponse(paper=paper, summary=summary)
