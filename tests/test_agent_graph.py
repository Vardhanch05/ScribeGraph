import os
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid4

import pytest


@pytest.fixture(autouse=True)
def force_mock_llm():
    original = os.environ.get("MOCK_LLM")
    os.environ["MOCK_LLM"] = "true"
    yield
    if original is not None:
        os.environ["MOCK_LLM"] = original
    else:
        del os.environ["MOCK_LLM"]

from sqlmodel import create_engine

from quantinsight.agent.graph import app, run_agent
from quantinsight.ingestion.pipeline import ingest_paper
from quantinsight.schemas.models import (
    ChunkType,
    CitedSummary,
    EquationUnit,
    PaperChunk,
    TableUnit,
)
from quantinsight.storage import chroma_store, sqlite_store
from quantinsight.storage.sqlite_store import get_agent_trace, init_db


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

    for patcher in active_patchers:
        patcher.stop()


@pytest.mark.anyio
async def test_agent_prose_query(temp_chroma, temp_db, mock_ingestion_setup):
    markdown_content = """# Section 1: Intro
    Multi-Head Relational Attention is a mechanism that computes relations on arbitrary graphs.
    """
    mock_ingestion_setup(markdown_content)

    paper_id, _ = await ingest_paper(
        arxiv_id="2303.11111",
        title="Paper A",
        authors=["Author A"],
        api_key="mock_key",
        groq_api_key="mock_key",
    )

    # 1. Prose Query
    query = "Explain how multi-head relational attention works."
    response = await run_agent(query, paper_ids=[paper_id])

    assert response.answer is not None
    assert "Mock draft answer" in response.answer
    assert response.self_correction_applied is False
    assert len(response.citations) > 0

    # Verify trace contains step steps: Planner, Retriever, Synthesizer, Verifier, Synthesizer
    assert len(response.trace) == 5
    nodes = [step.node_name for step in response.trace]
    assert nodes == ["Planner", "Retriever", "Synthesizer", "Verifier", "Synthesizer"]

    # Verify trace steps are persisted in SQLite (Task 33)
    persisted_trace = get_agent_trace(UUID(response.trace[0].input_summary.split("Query:")[0].strip()) if False else None)
    # We can inspect the table directly
    from sqlmodel import Session, select
    from quantinsight.storage.sqlite_store import AgentTraceStepDb
    with Session(temp_db) as session:
        steps = session.exec(select(AgentTraceStepDb).order_by(AgentTraceStepDb.step_index)).all()
        assert len(steps) == 5
        assert steps[0].node_name == "Planner"
        assert steps[1].node_name == "Retriever"


@pytest.mark.anyio
async def test_agent_equation_query(temp_chroma, temp_db, mock_ingestion_setup):
    markdown_content = """# Section 2: Formulas
    The scaling factor relation is:
    $$
    E = mc^2
    $$
    """
    mock_ingestion_setup(markdown_content)

    paper_id, _ = await ingest_paper(
        arxiv_id="2303.22222",
        title="Paper B",
        authors=["Author B"],
        api_key="mock_key",
        groq_api_key="mock_key",
    )

    # 2. Equation Query (triggers equation chunk search)
    query = "Show me the energy equation formula."
    response = await run_agent(query, paper_ids=[paper_id])

    assert response.answer is not None
    assert "Equation: $$\nE = mc^2\n$$" in response.answer or "Equation" in response.answer
    assert len(response.citations) > 0


@pytest.mark.anyio
async def test_agent_table_query(temp_chroma, temp_db, mock_ingestion_setup):
    markdown_content = """# Section 3: Results
    Table 1: Model score results.
    | Model | Score |
    |---|---|
    | Relational | 98.2 |
    """
    mock_ingestion_setup(markdown_content)

    paper_id, _ = await ingest_paper(
        arxiv_id="2303.33333",
        title="Paper C",
        authors=["Author C"],
        api_key="mock_key",
        groq_api_key="mock_key",
    )

    # 3. Table Query (triggers table chunk search)
    query = "What is the score model results table?"
    response = await run_agent(query, paper_ids=[paper_id])

    assert response.answer is not None
    assert "| Model | Score |" in response.answer
    assert len(response.citations) > 0


@pytest.mark.anyio
async def test_agent_no_evidence_fallback(temp_chroma, temp_db):
    # Database is empty, searching for anything will yield empty results
    query = "What is quantum gravity?"
    response = await run_agent(query, paper_ids=[uuid4()])

    assert response.answer == "No supporting evidence found in the ingested papers to answer this query."
    assert response.citations == []
    assert response.confidence_note == "No retrieved chunks."
    assert len(response.trace) == 5
    assert [s.node_name for s in response.trace] == ["Planner", "Retriever", "Synthesizer", "Verifier", "Synthesizer"]


@pytest.mark.anyio
async def test_agent_revision_loop(temp_chroma, temp_db, mock_ingestion_setup):
    markdown_content = """# Section 1: Intro
    Multi-Head Relational Attention is a mechanism that computes relations on arbitrary graphs.
    """
    mock_ingestion_setup(markdown_content)

    paper_id, _ = await ingest_paper(
        arxiv_id="2303.44444",
        title="Paper D",
        authors=["Author D"],
        api_key="mock_key",
        groq_api_key="mock_key",
    )

    # 5. Revision Query (forces revision in mock verifier)
    query = "Please revise the attention explanation."
    thread_id = uuid4()
    response = await run_agent(query, paper_ids=[paper_id], thread_id=thread_id)

    assert response.answer is not None
    assert response.self_correction_applied is True
    # Trace steps:
    # 0. Planner
    # 1. Retriever
    # 2. Synthesizer (draft 1)
    # 3. Verifier (triggers revision, count=1)
    # 4. Retriever (revision loop)
    # 5. Synthesizer (draft 2)
    # 6. Verifier (no revision, count=1)
    # 7. Synthesizer (final)
    # Total = 8 steps.
    assert len(response.trace) == 8
    nodes = [step.node_name for step in response.trace]
    assert nodes == [
        "Planner",
        "Retriever",
        "Synthesizer",
        "Verifier",
        "Retriever",
        "Synthesizer",
        "Verifier",
        "Synthesizer",
    ]

    # Verify that we can inspect thread state after completion (Task 32)
    config = {"configurable": {"thread_id": str(thread_id)}}
    from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
    from quantinsight.agent.graph import CHECKPOINT_DB_PATH, workflow
    async with AsyncSqliteSaver.from_conn_string(CHECKPOINT_DB_PATH) as checkpointer:
        local_app = workflow.compile(checkpointer=checkpointer)
        state = await local_app.aget_state(config)
    assert state.values is not None
    assert state.values.get("revision_count") == 1
    assert state.values.get("needs_revision") is False
    assert state.values.get("final_answer") is not None
    assert state.values.get("final_answer").answer == response.answer


@pytest.mark.anyio
async def test_agent_ambiguous_query(temp_chroma, temp_db, mock_ingestion_setup):
    # Ingest one paper
    markdown_content = "# Ambiguous Paper\nThis contains general information about machine learning systems."
    mock_ingestion_setup(markdown_content)
    paper_id, _ = await ingest_paper(
        arxiv_id="2303.55555",
        title="Paper E",
        authors=["Author E"],
        api_key="mock_key",
        groq_api_key="mock_key",
    )
    # Ambiguous query
    query = "What is it?"
    response = await run_agent(query, paper_ids=[paper_id])
    assert response.answer is not None
    assert "Mock draft answer" in response.answer or "Fallback" in response.answer


@pytest.mark.anyio
async def test_agent_multipaper_comparison(temp_chroma, temp_db, mock_ingestion_setup):
    # Ingest two papers
    markdown_content_1 = "# ResNet Paper\nResidual learning is deep and stable."
    markdown_content_2 = "# Attention Paper\nAttention is all you need for sequence models."

    mock_parse, mock_summary = mock_ingestion_setup(markdown_content_1)
    paper_id_1, _ = await ingest_paper(
        arxiv_id="2303.66666",
        title="Paper F",
        authors=["Author F"],
        api_key="mock_key",
        groq_api_key="mock_key",
    )

    # We must patch mock_parse's return value to return the second paper's markdown on the second ingest
    mock_parse.return_value = markdown_content_2
    paper_id_2, _ = await ingest_paper(
        arxiv_id="2303.77777",
        title="Paper G",
        authors=["Author G"],
        api_key="mock_key",
        groq_api_key="mock_key",
    )

    # Comparison query across both papers
    query = "Compare ResNet and Attention."
    response = await run_agent(query, paper_ids=[paper_id_1, paper_id_2])

    assert response.answer is not None
    # Verify that multi-hop was correctly set
    planner_step = response.trace[0]
    assert planner_step.node_name == "Planner"
    assert "Is Multihop: True" in planner_step.output_summary


@pytest.mark.anyio
async def test_verifier_context_truncation_prioritizes_cited_chunks():
    from quantinsight.agent.nodes.verifier import verifier_node
    from quantinsight.schemas.models import PaperChunk, ChunkType

    cited_id = uuid4()

    cited_chunk = PaperChunk(
        id=cited_id,
        paper_id=uuid4(),
        chunk_type=ChunkType.PROSE,
        content="Target cited content that must be included.",
        page_number=1,
        order_index=0,
    )
    # Create large uncited chunks that total > 10k chars (would fill budget if prioritized)
    uncited_chunks = [
        PaperChunk(
            id=uuid4(),
            paper_id=uuid4(),
            chunk_type=ChunkType.PROSE,
            content=f"Uncited prose chunk {i} " + ("X" * 1500),
            page_number=i,
            order_index=i,
        )
        for i in range(8)
    ]

    state = {
        "query": "Test query",
        "draft_answer": f"Draft stating factual claim [{cited_id}].",
        "retrieved_chunks": uncited_chunks + [cited_chunk],
        "retrieved_tables": [],
        "retrieved_equations": [],
        "revision_count": 0,
        "trace": [],
    }

    with patch("quantinsight.agent.nodes.verifier.is_mock_enabled", return_value=False):
        with patch("quantinsight.agent.nodes.verifier.call_groq", new_callable=AsyncMock) as mock_call_groq:
            mock_call_groq.return_value = '{"needs_revision": false, "verification_notes": ["Verified"]}'
            res = await verifier_node(state)
            
            # Verify call_groq was invoked
            assert mock_call_groq.call_count == 1
            _, kwargs = mock_call_groq.call_args
            user_prompt = kwargs.get("user_prompt", "")
            
            # Explicitly assert cited chunk survived truncation and is present in prompt
            assert "Target cited content that must be included." in user_prompt
            assert str(cited_id) in user_prompt
            assert res["needs_revision"] is False


@pytest.mark.anyio
async def test_verifier_degraded_mode_flagging():
    from quantinsight.agent.nodes.verifier import verifier_node
    from quantinsight.schemas.models import PaperChunk, ChunkType

    chunk = PaperChunk(
        id=uuid4(),
        paper_id=uuid4(),
        chunk_type=ChunkType.PROSE,
        content="Test content",
        page_number=1,
        order_index=0,
    )

    state = {
        "query": "Test query",
        "draft_answer": "Draft answer",
        "retrieved_chunks": [chunk],
        "retrieved_tables": [],
        "retrieved_equations": [],
        "revision_count": 0,
        "trace": [],
    }

    with patch("quantinsight.agent.nodes.verifier.is_mock_enabled", return_value=False):
        with patch("quantinsight.agent.nodes.verifier.call_groq", side_effect=RuntimeError("Groq 400 Context Limit")):
            res = await verifier_node(state)
            assert res["needs_revision"] is False
            assert any("DEGRADED VERIFICATION MODE" in note for note in res["verification_notes"])


@pytest.mark.anyio
async def test_llm_fallback_skips_context_and_tpd_limits():
    from quantinsight.agent.llm import call_groq

    with patch("quantinsight.agent.llm.is_mock_enabled", return_value=False):
        with patch("quantinsight.agent.llm._call_groq_chat_completion") as mock_completion:
            mock_completion.side_effect = [
                Exception("Rate limit 429 - tokens per day (TPD) exceeded"),
                "Successful fallback response",
            ]
            response = await call_groq("System", "User")
            assert response == "Successful fallback response"
            assert mock_completion.call_count == 2


