from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid4

import pytest

from quantinsight.ingestion.pipeline import ingest_paper
from quantinsight.schemas.models import CitedSummary
from quantinsight.storage import sqlite_store


@pytest.fixture(autouse=True)
def mock_db():
    from sqlmodel import create_engine

    test_engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}
    )
    with patch("quantinsight.storage.sqlite_store.engine", test_engine):
        sqlite_store.init_db()
        yield


@pytest.fixture
def mock_ingestion_deps():
    # Mock parse_pdf
    mock_raw_md = """# Introduction
This is a test paper with some math:
$$
E = mc^2
$$
And a table:
| Header 1 | Header 2 |
|---|---|
| A | B |
"""

    # Mock CitedSummary
    def make_mock_summary(paper_id):
        return CitedSummary(
            id=uuid4(),
            paper_id=paper_id,
            summary="A summary of the test paper.",
            key_claims=["Claim A", "Claim B"],
            supporting_chunk_ids=[],
            generated_at=datetime.now(UTC),
            model_used="mock-model",
        )

    with (
        patch(
            "quantinsight.ingestion.pipeline.parse_pdf",
            AsyncMock(return_value=mock_raw_md),
        ) as mock_parse,
        patch(
            "quantinsight.ingestion.pipeline.generate_cited_summary"
        ) as mock_summary_gen,
        patch(
            "quantinsight.ingestion.pipeline.save_embeddings", AsyncMock()
        ) as mock_save_emb,
        patch(
            "quantinsight.ingestion.pipeline.delete_paper_embeddings", AsyncMock()
        ) as mock_del_emb,
    ):
        mock_summary_gen.side_effect = lambda paper_id, chunks, api_key, model: (
            make_mock_summary(paper_id)
        )
        yield {
            "parse": mock_parse,
            "summary_gen": mock_summary_gen,
            "save_emb": mock_save_emb,
            "del_emb": mock_del_emb,
        }


@pytest.mark.anyio
async def test_ingest_paper_success(mock_ingestion_deps):
    arxiv_id = "2303.11111"
    paper_id, warnings = await ingest_paper(
        arxiv_id=arxiv_id,
        title="Test Paper",
        authors=["Author 1"],
        api_key="fake",
        groq_api_key="fake",
    )

    assert isinstance(paper_id, UUID)
    assert len(warnings) == 0

    # Check SQLite store
    paper = sqlite_store.get_paper_by_id(paper_id)
    assert paper is not None
    assert paper.arxiv_id == arxiv_id
    assert paper.title == "Test Paper"
    assert paper.authors == ["Author 1"]

    chunks = sqlite_store.get_paper_chunks(paper_id)
    # Expected: 4 chunks (Introduction, Equation, Prose, Table)
    assert len(chunks) == 4
    for idx, c in enumerate(chunks):
        assert c.order_index == idx
        assert c.paper_id == paper_id

    summary = sqlite_store.get_paper_summary(paper_id)
    assert summary is not None
    assert summary.summary == "A summary of the test paper."

    mock_ingestion_deps["save_emb"].assert_called_once()


@pytest.mark.anyio
async def test_ingest_paper_idempotency(mock_ingestion_deps):
    arxiv_id = "2303.22222"

    # First Ingest
    paper_id_1, _ = await ingest_paper(
        arxiv_id=arxiv_id,
        title="Original Title",
        authors=["Author A"],
        api_key="fake",
        groq_api_key="fake",
    )

    # Second Ingest: Change title/authors
    paper_id_2, _ = await ingest_paper(
        arxiv_id=arxiv_id,
        title="Updated Title",
        authors=["Author B"],
        api_key="fake",
        groq_api_key="fake",
    )

    # Assert same paper ID was used
    assert paper_id_1 == paper_id_2

    # Check SQLite metadata was updated
    paper = sqlite_store.get_paper_by_id(paper_id_1)
    assert paper is not None
    assert paper.title == "Updated Title"
    assert paper.authors == ["Author B"]

    # Check that chunks and elements were updated without duplicates
    chunks = sqlite_store.get_paper_chunks(paper_id_1)
    assert len(chunks) == 4  # Should still be 4, not 8!

    # Verify delete_paper_embeddings was called for the re-ingestion
    mock_ingestion_deps["del_emb"].assert_called_once_with(paper_id_1)
