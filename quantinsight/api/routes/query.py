import json
from uuid import uuid4
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from quantinsight.agent.graph import CHECKPOINT_DB_PATH, run_agent, workflow
from quantinsight.schemas.models import QueryRequest, QueryResponse
from quantinsight.storage.sqlite_store import save_agent_trace

router = APIRouter(prefix="/query", tags=["Query"])


@router.post("", response_model=QueryResponse)
async def query_agent(payload: QueryRequest) -> QueryResponse:
    """Execute the agent loop synchronously and return the full QueryResponse."""
    if not payload.query.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Query string cannot be empty.",
        )

    try:
        response = await run_agent(
            query=payload.query,
            paper_ids=payload.paper_ids,
        )
        return response
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Agent execution failed: {str(e)}",
        )


@router.post("/stream")
async def query_agent_stream(payload: QueryRequest):
    """Stream AgentTraceStep updates as Server-Sent Events (SSE) during execution."""
    if not payload.query.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Query string cannot be empty.",
        )

    thread_id = uuid4()
    config = {"configurable": {"thread_id": str(thread_id)}}

    initial_state = {
        "query": payload.query,
        "paper_ids": payload.paper_ids,
        "retrieved_chunks": [],
        "retrieved_tables": [],
        "retrieved_equations": [],
        "verification_notes": [],
        "needs_revision": False,
        "revision_count": 0,
        "trace": [],
    }

    async def event_generator():
        sent_indices = set()
        final_answer = None

        try:
            async with AsyncSqliteSaver.from_conn_string(CHECKPOINT_DB_PATH) as checkpointer:
                local_app = workflow.compile(checkpointer=checkpointer)
                async for chunk in local_app.astream(initial_state, config=config, stream_mode="updates"):
                    for node_name, state_update in chunk.items():
                        if isinstance(state_update, dict):
                            trace = state_update.get("trace", [])
                            for step in trace:
                                if step.step_index not in sent_indices:
                                    sent_indices.add(step.step_index)
                                    data = step.model_dump_json()
                                    yield f"event: trace_step\ndata: {data}\n\n"
                            if "final_answer" in state_update and state_update["final_answer"] is not None:
                                final_answer = state_update["final_answer"]

            if final_answer:
                save_agent_trace(thread_id, final_answer.trace)
                yield f"event: final_response\ndata: {final_answer.model_dump_json()}\n\n"
        except Exception as e:
            error_data = json.dumps({"error": str(e)})
            yield f"event: error\ndata: {error_data}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
