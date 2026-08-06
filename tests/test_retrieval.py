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
async def test_type_aware_routing(temp_chroma, temp_db, mock_ingestion_setup):
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

    # Equation search
    eq_results = await search(
        query="scaled dot-product formula",
        paper_ids=[paper_id],
        chunk_types=[ChunkType.EQUATION],
    )
    # Even if query is somewhat different, with type=EQUATION it must yield EquationUnit
    assert len(eq_results) > 0
    assert all(isinstance(r, EquationUnit) for r in eq_results)
    assert eq_results[0].latex == "$$\nE = mc^2\n$$"

    # Table search
    markdown_table = """# Results
Table 1: Energy data
| Mass | Energy |
|---|---|
| 1kg | 9e16J |
"""
    mock_ingestion_setup(markdown_table)
    table_paper_id, _ = await ingest_paper(
        arxiv_id="2303.77777",
        title="Energy Data",
        authors=["Einstein"],
        api_key="mock_key",
        groq_api_key="mock_key",
    )
    table_results = await search(
        query="comparison results table",
        paper_ids=[table_paper_id],
        chunk_types=[ChunkType.TABLE],
    )
    assert len(table_results) > 0
    assert all(isinstance(r, TableUnit) for r in table_results)

    # Prose search
    prose_results = await search(
        query="attention topology",
        paper_ids=[paper_id],
        chunk_types=[ChunkType.PROSE],
    )
    assert len(prose_results) > 0
    assert all(isinstance(r, PaperChunk) for r in prose_results)
    assert prose_results[0].chunk_type == ChunkType.PROSE


@pytest.mark.anyio
async def test_type_filter_hard_exclusion(temp_chroma, temp_db, mock_ingestion_setup):
    # Ingest content where a prose chunk is deliberately worded to be semantically closer
    # to an equation query than the actual equation.
    markdown_content = """# Section 1: Detailed Explanation
In this section, we describe the scaled dot-product formula in detail, which computes attention weights by multiplying queries and keys and applying scaling before softmax.

---
# Section 2: Mathematical Form
The exact calculation is represented by:
$$
\\text{Softmax}(Q K^T / \\sqrt{d_k})
$$
"""
    mock_ingestion_setup(markdown_content)

    paper_id, _ = await ingest_paper(
        arxiv_id="2303.55555",
        title="Formula Details",
        authors=["Alice"],
        api_key="mock_key",
        groq_api_key="mock_key",
    )

    # Query with chunk_types=[ChunkType.EQUATION] for "scaled dot-product formula"
    # Even though Section 1 prose matches the query words almost verbatim, it MUST be excluded.
    results = await search(
        query="scaled dot-product formula",
        paper_ids=[paper_id],
        chunk_types=[ChunkType.EQUATION],
    )
    assert len(results) > 0
    # Every single returned item must be EquationUnit (prose chunk strictly excluded)
    assert all(isinstance(r, EquationUnit) for r in results)
    assert not any(isinstance(r, PaperChunk) for r in results)


@pytest.mark.anyio
async def test_context_linkage_for_equations_and_tables(temp_chroma, temp_db, mock_ingestion_setup):
    markdown_content = """# Section 2: Methodology
The core calculation is done using the relation formula:
$$
\\sigma(Q K^T / \\sqrt{d_k})
$$
where Q, K, and V are matrices.

---
# Section 3: Results
We compare the performance of different models:
Table 1: Model comparison results.
| Model | Score |
|---|---|
| Relational | 98.2 |
"""
    mock_ingestion_setup(markdown_content)

    paper_id, _ = await ingest_paper(
        arxiv_id="2303.44444",
        title="Context Linkage",
        authors=["Alice"],
        api_key="mock_key",
        groq_api_key="mock_key",
    )

    # 1. Search for Equation and check surrounding context
    eq_results = await search(
        query="relation formula",
        paper_ids=[paper_id],
        chunk_types=[ChunkType.EQUATION],
    )
    assert len(eq_results) > 0
    equation = eq_results[0]
    assert isinstance(equation, EquationUnit)
    assert equation.surrounding_context is not None
    assert "The core calculation is done using the relation formula" in equation.surrounding_context

    # 2. Search for Table and check caption
    table_results = await search(
        query="Model comparison",
        paper_ids=[paper_id],
        chunk_types=[ChunkType.TABLE],
    )
    assert len(table_results) > 0
    table = table_results[0]
    assert isinstance(table, TableUnit)
    assert table.caption is not None
    assert "Table 1: Model comparison results" in table.caption


@pytest.mark.anyio
async def test_no_match_empty_result_handling(temp_chroma, temp_db, mock_ingestion_setup):
    markdown_content = """# Section 1: Intro
Attention is all you need for sequence transduction.
"""
    mock_ingestion_setup(markdown_content)

    paper_id, _ = await ingest_paper(
        arxiv_id="2303.33333",
        title="Simple Attention",
        authors=["Alice"],
        api_key="mock_key",
        groq_api_key="mock_key",
    )

    # Query with content that has no relevant match. It should execute successfully without crash.
    # Note: Since there is no similarity cutoff in the current implementation, it might return
    # the closest document, but we assert no exception is raised.
    try:
        results = await search(
            query="quantum error correction codes",
            paper_ids=[paper_id],
        )
        assert isinstance(results, list)
    except Exception as e:
        pytest.fail(f"Search raised an exception on no-match query: {e}")

    # Searching with non-existent paper ID should return an empty list
    empty_results = await search(
        query="attention",
        paper_ids=[uuid4()],
    )
    assert empty_results == []


@pytest.mark.anyio
async def test_multi_paper_filtering_variations(temp_chroma, temp_db, mock_ingestion_setup):
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

    # 1. Query with paper_ids=[paper_a_id] -> assert only Paper A's content is returned
    res_a = await search(query="relational or skip", paper_ids=[paper_a_id])
    assert len(res_a) > 0
    assert all(r.paper_id == paper_a_id for r in res_a)

    # 2. Query with paper_ids=[paper_b_id] -> assert only Paper B's content is returned
    res_b = await search(query="relational or skip", paper_ids=[paper_b_id])
    assert len(res_b) > 0
    assert all(r.paper_id == paper_b_id for r in res_b)

    # 3. Query with paper_ids=[paper_a_id, paper_b_id] -> assert content from both can be returned
    res_both = await search(query="relational or skip", paper_ids=[paper_a_id, paper_b_id])
    assert len(res_both) > 1
    paper_ids = {r.paper_id for r in res_both}
    assert paper_a_id in paper_ids
    assert paper_b_id in paper_ids

    # 4. Query with paper_ids=None (no filter) -> assert search runs across all ingested papers
    res_none = await search(query="relational or skip", paper_ids=None)
    assert len(res_none) > 1
    paper_ids_none = {r.paper_id for r in res_none}
    assert paper_a_id in paper_ids_none
    assert paper_b_id in paper_ids_none

    # 5. Query with paper_ids=[] (explicit empty list) -> assert this returns no results (empty list), distinct from None
    res_empty_list = await search(query="relational or skip", paper_ids=[])
    assert res_empty_list == []
