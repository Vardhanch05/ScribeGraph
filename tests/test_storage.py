from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlmodel import Session, create_engine, select

from quantinsight.schemas.models import (
    ChunkType,
    Citation,
    CitedSummary,
    EquationUnit,
    PaperChunk,
    SourcePaper,
    TableUnit,
)
from quantinsight.storage import sqlite_store
from quantinsight.storage.sqlite_store import (
    CitationDb,
    CitedSummaryDb,
    EquationUnitDb,
    PaperChunkDb,
    SourcePaperDb,
    TableUnitDb,
    clean_paper_child_records,
    get_paper_by_arxiv_id,
    get_paper_by_id,
    get_paper_chunks,
    get_paper_summary,
    init_db,
    list_all_papers,
    save_paper_elements,
    save_paper_metadata,
)


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


def test_save_and_retrieve_paper(temp_db):
    paper_id = uuid4()
    paper = SourcePaper(
        id=paper_id,
        arxiv_id="2303.12345",
        title="Test Paper Title",
        authors=["Author One", "Author Two"],
        source_url="https://arxiv.org/abs/2303.12345",
        ingested_at=datetime.now(UTC),
        raw_markdown_path="/dummy/path/raw.md",
        page_count=5,
    )

    # Save paper metadata
    save_paper_metadata(paper)

    # Retrieve by ID
    retrieved = get_paper_by_id(paper_id)
    assert retrieved is not None
    assert retrieved.id == paper_id
    assert retrieved.title == "Test Paper Title"
    assert retrieved.authors == ["Author One", "Author Two"]

    # Retrieve by arXiv ID
    retrieved_arxiv = get_paper_by_arxiv_id("2303.12345")
    assert retrieved_arxiv is not None
    assert retrieved_arxiv.id == paper_id

    # Check listing papers
    papers = list_all_papers()
    assert len(papers) == 1
    assert papers[0].id == paper_id


def test_save_paper_elements_and_cascade(temp_db):
    paper_id = uuid4()
    paper = SourcePaper(
        id=paper_id,
        arxiv_id="2303.54321",
        title="Test Elements Paper",
        authors=["Author Key"],
        source_url=None,
        ingested_at=datetime.now(UTC),
        raw_markdown_path="/dummy/path/raw2.md",
        page_count=2,
    )
    save_paper_metadata(paper)

    # Create chunks
    chunk_id = uuid4()
    chunk = PaperChunk(
        id=chunk_id,
        paper_id=paper_id,
        chunk_type=ChunkType.PROSE,
        content="This is prose content.",
        page_number=1,
        section_title="Intro",
        order_index=0,
    )

    # Create table
    table_id = uuid4()
    table = TableUnit(
        id=table_id,
        paper_id=paper_id,
        chunk_id=chunk_id,
        caption="A test table",
        headers=["Col1", "Col2"],
        rows=[["Val1", "Val2"]],
        page_number=1,
    )

    # Create equation
    eq_id = uuid4()
    eq = EquationUnit(
        id=eq_id,
        paper_id=paper_id,
        chunk_id=chunk_id,
        latex="y = mx + c",
        surrounding_context="Definition of a straight line",
        equation_label="eq1",
        page_number=1,
    )

    # Create citation
    cit_id = uuid4()
    citation = Citation(
        id=cit_id,
        paper_id=paper_id,
        cited_text="Standard result [1]",
        cited_work_raw="[1] Doe et al., 2020",
        resolved_arxiv_id=None,
    )

    # Create summary
    summary_id = uuid4()
    summary = CitedSummary(
        id=summary_id,
        paper_id=paper_id,
        summary="A summary of the paper.",
        key_claims=["Claim 1"],
        supporting_chunk_ids=[chunk_id],
        generated_at=datetime.now(UTC),
        model_used="test-model",
    )

    save_paper_elements([chunk], [table], [eq], [citation], summary)

    # Verify retrieval
    chunks = get_paper_chunks(paper_id)
    assert len(chunks) == 1
    assert chunks[0].id == chunk_id

    ret_summary = get_paper_summary(paper_id)
    assert ret_summary is not None
    assert ret_summary.summary == "A summary of the paper."
    assert ret_summary.supporting_chunk_ids == [chunk_id]

    # Check count in DB
    with Session(temp_db) as session:
        assert len(session.exec(select(PaperChunkDb)).all()) == 1
        assert len(session.exec(select(TableUnitDb)).all()) == 1
        assert len(session.exec(select(EquationUnitDb)).all()) == 1
        assert len(session.exec(select(CitationDb)).all()) == 1
        assert len(session.exec(select(CitedSummaryDb)).all()) == 1

    # Clean paper child records
    clean_paper_child_records(paper_id)

    # Verify child records deleted but paper still exists
    chunks_after = get_paper_chunks(paper_id)
    assert len(chunks_after) == 0
    assert get_paper_summary(paper_id) is None

    with Session(temp_db) as session:
        assert len(session.exec(select(PaperChunkDb)).all()) == 0
        assert len(session.exec(select(TableUnitDb)).all()) == 0
        assert len(session.exec(select(EquationUnitDb)).all()) == 0
        assert len(session.exec(select(CitationDb)).all()) == 0
        assert len(session.exec(select(CitedSummaryDb)).all()) == 0

        # Source paper must still exist
        assert len(session.exec(select(SourcePaperDb)).all()) == 1
