import os
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid4

import pytest
from sqlmodel import create_engine

from quantinsight.ingestion.pipeline import ingest_paper
from quantinsight.schemas.models import ChunkType, CitedSummary, EquationUnit, PaperChunk, TableUnit
from quantinsight.storage import chroma_store, sqlite_store
from quantinsight.storage.chroma_store import search
from quantinsight.storage.sqlite_store import init_db


@pytest.fixture
def temp_db():
    # Use an in-memory database to test database logic cleanly
    test_engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}
    )

    # Patch the engine in sqlite_store
    original_engine = sqlite_store.engine
    sqlite_store.engine = test_engine

    # Initialize the database schema
    init_db()

    yield test_engine

    # Restore original engine
    sqlite_store.engine = original_engine


@pytest.fixture
def temp_chroma(tmp_path):
    test_chroma_dir = str(tmp_path / "chroma")
    original_chroma_dir = chroma_store.CHROMA_DIR
    chroma_store.CHROMA_DIR = test_chroma_dir

    yield test_chroma_dir

    # Restore original path
    chroma_store.CHROMA_DIR = original_chroma_dir


@pytest.fixture
def mock_ingestion_setup():
    """Factory fixture to patch parse_pdf and generate_cited_summary with custom markdown."""
    active_patchers = []

    def _setup(markdown_content: str):
        # Mock CitedSummary generation
        def make_mock_summary(paper_id):
            return CitedSummary(
                id=uuid4(),
                paper_id=paper_id,
                summary="A summary of the paper.",
                key_claims=["Key Claim"],
                supporting_chunk_ids=[],
                generated_at=datetime.now(UTC),
                model_used="mock-model",
            )

        parse_patcher = patch(
            "quantinsight.ingestion.pipeline.parse_pdf",
            AsyncMock(return_value=markdown_content),
        )
        summary_patcher = patch(
            "quantinsight.ingestion.pipeline.generate_cited_summary"
        )

        mock_parse = parse_patcher.start()
        mock_summary_gen = summary_patcher.start()
        mock_summary_gen.side_effect = lambda paper_id, chunks, api_key, model: make_mock_summary(paper_id)

        active_patchers.extend([parse_patcher, summary_patcher])
        return mock_parse, mock_summary_gen

    yield _setup

    # Clean up patchers after test completes
    for patcher in active_patchers:
        patcher.stop()


@pytest.mark.anyio
async def test_end_to_end_ingestion_and_retrieval(temp_chroma, temp_db, mock_ingestion_setup):
    # 1. Define a mock paper markdown with prose, equation, and table
    markdown_content = """# Section 1: Introduction
Multi-Head Relational Attention allows the model to compute attention across arbitrary graph topologies.
We define this relation explicitly in our model.

---
# Section 2: Methodology
The core calculation is done using the relation formula:
$$
\\sigma(Q K^T / \\sqrt{d_k})
$$
where Q, K, and V are query, key, and value matrices.

---
# Section 3: Results
We compare the performance of different models:
Table 1: Model comparison results.
| Model | Score | Accuracy |
|---|---|---|
| Relational | 98.2 | 0.95 |
| Baseline | 85.1 | 0.81 |
"""

    mock_ingestion_setup(markdown_content)

    # Ingest the mock paper
    paper_id, warnings = await ingest_paper(
        arxiv_id="2303.99999",
        title="Attention and Topology",
        authors=["Alice", "Bob"],
        api_key="mock_key",
        groq_api_key="mock_key",
    )

    assert isinstance(paper_id, UUID)
    assert len(warnings) == 0

    # 2. Test semantic retrieval on prose content
    prose_results = await search(
        query="multi-head relational attention topologies",
        paper_ids=[paper_id],
        chunk_types=[ChunkType.PROSE],
    )
    assert len(prose_results) > 0
    assert isinstance(prose_results[0], PaperChunk)
    assert "Relational Attention" in prose_results[0].content

    # 3. Test type-aware routing for EquationUnit
    equation_results = await search(
        query="scaled dot-product formula with softmax",
        paper_ids=[paper_id],
        chunk_types=[ChunkType.EQUATION],
    )
    assert len(equation_results) > 0
    assert isinstance(equation_results[0], EquationUnit)
    assert "\\sigma" in equation_results[0].latex

    # 4. Test type-aware routing for TableUnit
    table_results = await search(
        query="comparison of model results",
        paper_ids=[paper_id],
        chunk_types=[ChunkType.TABLE],
    )
    assert len(table_results) > 0
    assert isinstance(table_results[0], TableUnit)
    assert "Relational" in table_results[0].rows[0][0]
    assert "Score" in table_results[0].headers


@pytest.mark.anyio
async def test_retrieval_routing_prioritization(temp_chroma, temp_db, mock_ingestion_setup):
    # Verify that searching for equations without specified chunk types prioritizes EquationUnit semantically
    markdown_content = """# Intro
Prose content discussing model parameters.

---
# Formula Section
The equation of energy-mass equivalence:
$$
E = mc^2
$$
This defines the relationship between mass and energy.
"""
    mock_ingestion_setup(markdown_content)

    paper_id, _ = await ingest_paper(
        arxiv_id="2303.88888",
        title="Energy Equivalence",
        authors=["Einstein"],
        api_key="mock_key",
        groq_api_key="mock_key",
    )

    # Searching with EQUATION chunk type should return EquationUnit
    eq_search = await search(
        query="E = mc^2 equation",
        paper_ids=[paper_id],
        chunk_types=[ChunkType.EQUATION],
    )
    assert len(eq_search) > 0
    assert isinstance(eq_search[0], EquationUnit)

    # Searching with PROSE chunk type should return PaperChunk
    prose_search = await search(
        query="Einstein energy equation discussion",
        paper_ids=[paper_id],
        chunk_types=[ChunkType.PROSE],
    )
    assert len(prose_search) > 0
    assert isinstance(prose_search[0], PaperChunk)


@pytest.mark.anyio
async def test_retrieval_multi_paper_filtering(temp_chroma, temp_db, mock_ingestion_setup):
    # Ingest Paper A
    markdown_a = """# Intro A
This is Paper A discussing relational attention mechanism.
"""
    mock_ingestion_setup(markdown_a)
    paper_a_id, _ = await ingest_paper(
        arxiv_id="2303.11111",
        title="Paper A",
        authors=["Author A"],
        api_key="mock_key",
        groq_api_key="mock_key",
    )

    # Ingest Paper B
    markdown_b = """# Intro B
This is Paper B discussing residual skip connections.
"""
    mock_ingestion_setup(markdown_b)
    paper_b_id, _ = await ingest_paper(
        arxiv_id="2303.22222",
        title="Paper B",
        authors=["Author B"],
        api_key="mock_key",
        groq_api_key="mock_key",
    )

    # Search filtering by Paper A
    res_a = await search(
        query="attention or skip connections",
        paper_ids=[paper_a_id],
    )
    assert len(res_a) > 0
    assert all(r.paper_id == paper_a_id for r in res_a)
    assert "Paper A" in res_a[0].content

    # Search filtering by Paper B
    res_b = await search(
        query="attention or skip connections",
        paper_ids=[paper_b_id],
    )
    assert len(res_b) > 0
    assert all(r.paper_id == paper_b_id for r in res_b)
    assert "Paper B" in res_b[0].content

    # Search with empty/None paper list (should return results from both papers)
    res_all = await search(
        query="Paper",
        paper_ids=None,
    )
    assert len(res_all) > 1
    paper_ids = {r.paper_id for r in res_all}
    assert paper_a_id in paper_ids
    assert paper_b_id in paper_ids
