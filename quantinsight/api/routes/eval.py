from fastapi import APIRouter, HTTPException, status

from scripts.run_eval import execute_evaluation

router = APIRouter(prefix="/eval", tags=["Evaluation"])


@router.post("/run")
async def run_eval_suite():
    """Trigger automated RAGAS benchmark evaluation suite."""
    try:
        results = await execute_evaluation()
        return results
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Evaluation failed: {str(e)}",
        )
