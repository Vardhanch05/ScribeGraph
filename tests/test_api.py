from unittest.mock import AsyncMock, patch
from uuid import uuid4
import pytest
from fastapi import APIRouter
from fastapi.testclient import TestClient
from pydantic import BaseModel

from quantinsight.api.main import create_app
from quantinsight.schemas.models import (
    AgentTraceStep,
    CitedSummary,
    QueryResponse,
    SourcePaper,
)


class DummyValidationModel(BaseModel):
    name: str
    age: int


@pytest.fixture
def client():
    app = create_app()

    router = APIRouter()

    @router.post("/test-validation")
    def test_validation(data: DummyValidationModel):
        return {"status": "ok"}

    @router.get("/test-generic-error")
    def test_generic_error():
        raise RuntimeError("Something went wrong internally.")

    app.include_router(router)

    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


def test_root(client):
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["app"] == "ScribeGraph Core API"


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_404_not_found(client):
    response = client.get("/non-existent-route-path")
    assert response.status_code == 404
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "NOT_FOUND"


def test_validation_error(client):
    response = client.post("/test-validation", json={"age": "not-a-number"})
    assert response.status_code == 422
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "UNPROCESSABLE_ENTITY"


def test_generic_error(client):
    response = client.get("/test-generic-error")
    assert response.status_code == 500
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "INTERNAL_SERVER_ERROR"


def test_list_papers(client):
    response = client.get("/papers")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_get_paper_not_found(client):
    fake_id = uuid4()
    response = client.get(f"/papers/{fake_id}")
    assert response.status_code == 404


@patch("quantinsight.api.routes.papers.get_paper_by_id")
@patch("quantinsight.api.routes.papers.get_paper_summary")
def test_get_paper_detail(mock_summary, mock_paper, client):
    p_id = uuid4()
    mock_paper.return_value = SourcePaper(
        id=p_id,
        title="Test Paper",
        authors=["Author A"],
        raw_markdown_path="/artifacts/test/raw.md",
        page_count=5,
    )
    mock_summary.return_value = CitedSummary(
        paper_id=p_id,
        summary="Test summary",
        key_claims=["Claim 1"],
        supporting_chunk_ids=[],
        model_used="test-model",
    )

    response = client.get(f"/papers/{p_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["paper"]["title"] == "Test Paper"
    assert data["summary"]["summary"] == "Test summary"


def test_ingest_bad_request(client):
    response = client.post("/ingest", data={})
    assert response.status_code == 400


@patch("quantinsight.api.routes.ingest.ingest_paper", new_callable=AsyncMock)
def test_ingest_success(mock_ingest, client):
    p_id = uuid4()
    mock_ingest.return_value = (p_id, [])

    response = client.post("/ingest", data={"arxiv_id": "1706.03762"})
    assert response.status_code == 202
    data = response.json()
    assert data["paper_id"] == str(p_id)
    assert data["status"] == "completed"


def test_query_empty_bad_request(client):
    response = client.post("/query", json={"query": "   ", "paper_ids": []})
    assert response.status_code == 400


@patch("quantinsight.api.routes.query.run_agent", new_callable=AsyncMock)
def test_query_success(mock_run, client):
    expected_resp = QueryResponse(
        answer="Attention is all you need.",
        citations=[],
        trace=[
            AgentTraceStep(
                step_index=1,
                node_name="planner",
                input_summary="Query",
                output_summary="Plan",
            )
        ],
        self_correction_applied=False,
    )
    mock_run.return_value = expected_resp

    response = client.post("/query", json={"query": "What is self-attention?", "paper_ids": []})
    assert response.status_code == 200
    data = response.json()
    assert data["answer"] == "Attention is all you need."
    assert len(data["trace"]) == 1


@patch("quantinsight.api.routes.query.workflow.compile")
def test_query_stream_error_handling(mock_compile, client):
    mock_app = AsyncMock()
    
    async def failing_astream(*args, **kwargs):
        raise RuntimeError("Simulated SSE pipeline failure")
        yield {}  # make it an async generator

    mock_app.astream = failing_astream
    mock_compile.return_value = mock_app

    response = client.post(
        "/query/stream",
        json={"query": "What is attention?", "paper_ids": []},
    )
    assert response.status_code == 200
    text = response.text
    assert "event: error" in text
    assert "Simulated SSE pipeline failure" in text


@pytest.mark.anyio
async def test_mcp_invalid_uuid_handling():
    from quantinsight.mcp_server.server import (
        ask_quantinsight,
        get_equation_context,
        get_paper_summary,
        search_papers,
    )

    invalid_uuid = "invalid-uuid-string"

    res_search = await search_papers(query="test", paper_ids=[invalid_uuid])
    assert len(res_search) == 1
    assert "error" in res_search[0]
    assert "Invalid paper_id UUID format" in res_search[0]["error"]

    res_summary = await get_paper_summary(paper_id=invalid_uuid)
    assert "error" in res_summary
    assert "Invalid paper_id UUID format" in res_summary["error"]

    res_eq = await get_equation_context(paper_id=invalid_uuid)
    assert "error" in res_eq
    assert "Invalid paper_id UUID format" in res_eq["error"]

    res_ask = await ask_quantinsight(query="test", paper_ids=[invalid_uuid])
    assert "error" in res_ask
    assert "Invalid paper_id UUID format" in res_ask["error"]

