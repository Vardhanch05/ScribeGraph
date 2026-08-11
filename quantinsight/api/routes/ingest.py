from uuid import UUID
from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status

from quantinsight.ingestion.pipeline import ingest_paper
from quantinsight.schemas.models import IngestResponse, SourcePaper
from quantinsight.storage.sqlite_store import get_paper_by_id

router = APIRouter(prefix="/ingest", tags=["Ingestion"])


@router.post("", response_model=IngestResponse, status_code=status.HTTP_202_ACCEPTED)
async def ingest(
    arxiv_id: str | None = Form(default=None),
    file: UploadFile | None = File(default=None),
) -> IngestResponse:
    """Trigger paper ingestion via arXiv ID or PDF file upload."""
    if not arxiv_id and not file:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either arxiv_id or file upload must be provided.",
        )

    pdf_bytes = None
    if file:
        pdf_bytes = await file.read()

    try:
        paper_id, warnings = await ingest_paper(
            arxiv_id=arxiv_id,
            pdf_bytes=pdf_bytes,
        )
        return IngestResponse(
            paper_id=paper_id,
            status="completed",
            warnings=warnings,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ingestion failed: {str(e)}",
        )


@router.get("/{paper_id}/status")
async def get_ingest_status(paper_id: UUID) -> dict[str, str | SourcePaper]:
    """Check ingestion status of a given paper."""
    paper = get_paper_by_id(paper_id)
    if not paper:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Paper with ID {paper_id} not found.",
        )
    return {
        "paper_id": str(paper_id),
        "status": "completed",
        "paper": paper,
    }
