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


@pytest.fixture
def temp_chroma(tmp_path):
    from quantinsight.storage import chroma_store

    test_chroma_dir = str(tmp_path / "chroma")
    original_chroma_dir = chroma_store.CHROMA_DIR
    chroma_store.CHROMA_DIR = test_chroma_dir

    yield test_chroma_dir

    # Restore original path
    chroma_store.CHROMA_DIR = original_chroma_dir


@pytest.mark.anyio
async def test_save_and_delete_embeddings(temp_chroma):
    import uuid

    from quantinsight.schemas.models import (
        ChunkType,
        EquationUnit,
        PaperChunk,
        TableUnit,
    )
    from quantinsight.storage.chroma_store import (
        delete_paper_embeddings,
        get_chroma_client,
        save_embeddings,
    )

    paper_id = uuid.uuid4()

    # 1. Create a prose chunk, a table chunk, and an equation chunk
    chunk_prose_id = uuid.uuid4()
    chunk_prose = PaperChunk(
        id=chunk_prose_id,
        paper_id=paper_id,
        chunk_type=ChunkType.PROSE,
        content="This is a prose chunk describing attention mechanism.",
        page_number=1,
        section_title="Introduction",
        order_index=0,
    )

    chunk_table_id = uuid.uuid4()
    chunk_table = PaperChunk(
        id=chunk_table_id,
        paper_id=paper_id,
        chunk_type=ChunkType.TABLE,
        content="This chunk contains a table of experiment results.",
        page_number=2,
        section_title="Experiments",
        order_index=1,
    )

    chunk_eq_id = uuid.uuid4()
    chunk_eq = PaperChunk(
        id=chunk_eq_id,
        paper_id=paper_id,
        chunk_type=ChunkType.EQUATION,
        content="This chunk contains the main formula.",
        page_number=3,
        section_title="Method",
        order_index=2,
    )

    # Create TableUnit and EquationUnit
    table = TableUnit(
        id=uuid.uuid4(),
        paper_id=paper_id,
        chunk_id=chunk_table_id,
        caption="Experiment results",
        headers=["Model", "Accuracy"],
        rows=[["Baseline", "0.85"], ["Ours", "0.92"]],
        page_number=2,
    )

    eq = EquationUnit(
        id=uuid.uuid4(),
        paper_id=paper_id,
        chunk_id=chunk_eq_id,
        latex="E = mc^2",
        surrounding_context="Relativistic energy-mass relation",
        page_number=3,
    )

    chunks = [chunk_prose, chunk_table, chunk_eq]

    # 2. Save embeddings
    await save_embeddings(chunks, [table], [eq])

    # Assert embedding_ids are populated
    assert chunk_prose.embedding_id == str(chunk_prose_id)
    assert chunk_table.embedding_id == str(chunk_table_id)
    assert chunk_eq.embedding_id == str(chunk_eq_id)

    # 3. Retrieve from Chroma to verify they are saved
    client = get_chroma_client()

    prose_coll = client.get_collection("prose_chunks")
    table_coll = client.get_collection("table_chunks")
    eq_coll = client.get_collection("equation_chunks")

    # Check prose collection
    prose_res = prose_coll.get(ids=[str(chunk_prose_id)])
    assert len(prose_res["ids"]) == 1
    assert prose_res["metadatas"][0]["paper_id"] == str(paper_id)
    assert prose_res["metadatas"][0]["page_number"] == 1
    assert "attention mechanism" in prose_res["documents"][0]

    # Check table collection
    table_res = table_coll.get(ids=[str(chunk_table_id)])
    assert len(table_res["ids"]) == 1
    assert table_res["metadatas"][0]["paper_id"] == str(paper_id)
    assert "Experiment results" in table_res["documents"][0]

    # Check equation collection
    eq_res = eq_coll.get(ids=[str(chunk_eq_id)])
    assert len(eq_res["ids"]) == 1
    assert eq_res["metadatas"][0]["paper_id"] == str(paper_id)
    assert "E = mc^2" in eq_res["documents"][0]

    # 4. Delete paper embeddings
    await delete_paper_embeddings(paper_id)

    # Verify they are deleted
    prose_res_after = prose_coll.get(ids=[str(chunk_prose_id)])
    assert len(prose_res_after["ids"]) == 0

    table_res_after = table_coll.get(ids=[str(chunk_table_id)])
    assert len(table_res_after["ids"]) == 0

    eq_res_after = eq_coll.get(ids=[str(chunk_eq_id)])
    assert len(eq_res_after["ids"]) == 0
