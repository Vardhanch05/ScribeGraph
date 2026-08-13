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
            args, kwargs = mock_call_groq.call_args
            user_prompt = kwargs.get("user_prompt") or (args[1] if len(args) > 1 else "")
            
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


@pytest.mark.anyio
async def test_synthesizer_fallback_and_degraded_confidence_notes():
    from quantinsight.agent.nodes.synthesizer import synthesizer_node
    from quantinsight.schemas.models import PaperChunk, ChunkType

    paper_id = uuid4()
    chunk = PaperChunk(
        id=uuid4(),
        paper_id=paper_id,
        chunk_type=ChunkType.PROSE,
        content="Sample evidence content.",
        page_number=1,
        order_index=0,
    )

    # Test Fallback Draft Confidence Note
    fallback_state = {
        "query": "What is the benchmark score?",
        "paper_ids": [paper_id],
        "draft_answer": f"Fallback draft answer for query: 'What is the benchmark score?' due to API issue. [{chunk.id}]",
        "retrieved_chunks": [chunk],
        "retrieved_tables": [],
        "retrieved_equations": [],
        "verification_notes": [],
        "revision_count": 1,
        "trace": [],
    }

    res_fallback = await synthesizer_node(fallback_state)
    final_ans_fallback = res_fallback["final_answer"]
    assert final_ans_fallback.self_correction_applied is False
    assert "Generation failed — fallback response returned due to API issue." in final_ans_fallback.confidence_note

    # Test Degraded Verification Mode Confidence Note
    degraded_state = {
        "query": "What is the benchmark score?",
        "paper_ids": [paper_id],
        "draft_answer": f"Valid answer string [{chunk.id}]",
        "retrieved_chunks": [chunk],
        "retrieved_tables": [],
        "retrieved_equations": [],
        "verification_notes": ["⚠️ DEGRADED VERIFICATION MODE: Verifier check bypassed due to API exception."],
        "revision_count": 1,
        "trace": [],
    }

    res_degraded = await synthesizer_node(degraded_state)
    final_ans_degraded = res_degraded["final_answer"]
    assert final_ans_degraded.self_correction_applied is False
    assert "Degraded Verification Mode" in final_ans_degraded.confidence_note


@pytest.mark.anyio
async def test_retrieval_no_starvation():
    from quantinsight.storage.chroma_store import save_embeddings, search
    from quantinsight.storage.sqlite_store import save_paper_elements
    from quantinsight.schemas.models import PaperChunk, TableUnit, ChunkType, CitedSummary

    paper_id = uuid4()
    chunks = []
    tables = []

    for idx in range(10):
        c_id = uuid4()
        c = PaperChunk(
            id=c_id,
            paper_id=paper_id,
            chunk_type=ChunkType.PROSE,
            content=f"Prose chunk content {idx} discussing benchmark models and evaluation results.",
            page_number=1,
            order_index=idx,
        )
        chunks.append(c)

    for idx in range(5):
        t_chunk_id = uuid4()
        t_chunk = PaperChunk(
            id=t_chunk_id,
            paper_id=paper_id,
            chunk_type=ChunkType.TABLE,
            content=f"Table chunk content {idx}",
            page_number=1,
            order_index=10 + idx,
        )
        t_unit = TableUnit(
            id=uuid4(),
            paper_id=paper_id,
            chunk_id=t_chunk_id,
            caption=f"Benchmark Accuracy Table {idx}",
            headers=["Model", "Accuracy"],
            rows=[["Baseline", "85%"], ["Ours", "92%"]],
            page_number=1,
        )
        chunks.append(t_chunk)
        tables.append(t_unit)

    summary = CitedSummary(
        id=uuid4(),
        paper_id=paper_id,
        summary="Summary text.",
        key_claims=["Claim 1"],
        supporting_chunk_ids=[chunks[0].id],
        model_used="gpt-4o",
    )

    save_paper_elements(chunks, tables, [], [], summary)
    await save_embeddings(chunks, tables, [])

    # Query ChromaDB with chunk_types = [PROSE, TABLE]
    results = await search(
        query="benchmark accuracy score table",
        paper_ids=[paper_id],
        chunk_types=[ChunkType.PROSE, ChunkType.TABLE],
        limit=5,
    )

    prose_results = [r for r in results if isinstance(r, PaperChunk)]
    table_results = [r for r in results if isinstance(r, TableUnit)]

    # Assert that BOTH prose chunks and table units are retrieved (no starvation)
    assert len(prose_results) > 0
    assert len(table_results) > 0


@pytest.mark.anyio
async def test_agent_revision_cap_hard_limit(temp_chroma, temp_db, mock_ingestion_setup):
    markdown_content = "# Section 1\nProse content."
    mock_ingestion_setup(markdown_content)
    paper_id, _ = await ingest_paper(
        arxiv_id="2303.99991",
        title="Cap Test Paper",
        authors=["Alice"],
        api_key="mock_key",
        groq_api_key="mock_key",
    )

    with patch("quantinsight.agent.nodes.verifier.is_mock_enabled", return_value=False):
        with patch("quantinsight.agent.nodes.verifier.call_groq", new_callable=AsyncMock) as mock_verifier_llm:
            # Always force verifier to demand revision
            mock_verifier_llm.return_value = '{"needs_revision": true, "verification_notes": ["Always needs revision."]}'
            response = await run_agent("Test query requiring revision", paper_ids=[paper_id])

            # Confirm loop terminated at revision cap 2
            rev_steps = [s for s in response.trace if s.node_name == "Verifier"]
            assert len(rev_steps) == 2
            assert response.answer is not None


@pytest.mark.anyio
async def test_synthesizer_verifier_evidence_budget_parity():
    from quantinsight.agent.nodes.synthesizer import synthesizer_node
    from quantinsight.agent.nodes.verifier import verifier_node
    from quantinsight.schemas.models import PaperChunk, ChunkType

    paper_id = uuid4()
    # Create evidence totaling ~11,000 characters (between 10k and 12k)
    chunks = [
        PaperChunk(
            id=uuid4(),
            paper_id=paper_id,
            chunk_type=ChunkType.PROSE,
            content=f"Chunk {i} " + ("Z" * 2000),
            page_number=i,
            order_index=i,
        )
        for i in range(5)
    ]

    state = {
        "query": "Budget parity test query",
        "draft_answer": f"Draft answer with citation [{chunks[4].id}]",
        "retrieved_chunks": chunks,
        "retrieved_tables": [],
        "retrieved_equations": [],
        "verification_notes": [],
        "revision_count": 0,
        "trace": [],
    }

    with patch("quantinsight.agent.nodes.verifier.is_mock_enabled", return_value=False):
        with patch("quantinsight.agent.nodes.verifier.call_groq", new_callable=AsyncMock) as mock_verifier:
            mock_verifier.return_value = '{"needs_revision": false, "verification_notes": ["OK"]}'
            await verifier_node(state)
            
            # Verify 5th chunk (at ~10,000 char threshold) was included in Verifier prompt
            _, kwargs = mock_verifier.call_args
            prompt = kwargs.get("user_prompt", "")
            assert str(chunks[4].id) in prompt

    synth_state = dict(state)
    synth_state["draft_answer"] = None

    with patch("quantinsight.agent.nodes.synthesizer.is_mock_enabled", return_value=False):
        with patch("quantinsight.agent.nodes.synthesizer.call_groq", new_callable=AsyncMock) as mock_synth:
            mock_synth.return_value = '{"answer": "Draft", "citations": []}'
            await synthesizer_node(synth_state)
            _, kwargs = mock_synth.call_args
            prompt = kwargs.get("user_prompt", "")
            assert str(chunks[4].id) in prompt


@pytest.mark.anyio
async def test_synthesizer_strips_hallucinated_citations():
    from quantinsight.agent.nodes.synthesizer import synthesizer_node
    from quantinsight.schemas.models import PaperChunk, ChunkType

    valid_id = uuid4()
    fabricated_uuid = UUID("12345678-9999-4444-8888-123456789999")

    valid_chunk = PaperChunk(
        id=valid_id,
        paper_id=uuid4(),
        chunk_type=ChunkType.PROSE,
        content="Valid evidence content.",
        page_number=1,
        order_index=0,
    )

    state = {
        "query": "Test hallucination query",
        "draft_answer": f"Supported claim [{valid_id}]. Fabricated claim [{fabricated_uuid}].",
        "retrieved_chunks": [valid_chunk],
        "retrieved_tables": [],
        "retrieved_equations": [],
        "verification_notes": [],
        "needs_revision": False,
        "revision_count": 0,
        "trace": [],
    }

    res = await synthesizer_node(state)
    final_ans = res["final_answer"]

    assert str(fabricated_uuid) not in final_ans.answer
    assert fabricated_uuid not in final_ans.citations
    assert valid_id in final_ans.citations


@pytest.mark.anyio
async def test_llm_multi_model_fallback_tries_all_candidates():
    from quantinsight.agent.llm import call_groq, reset_depleted_models

    reset_depleted_models()
    attempted_models = []

    async def mock_completion(client, candidate, messages, response_json=True):
        attempted_models.append(candidate)
        raise Exception("429 Rate limit - tokens per day (TPD) limit reached")

    with patch("quantinsight.agent.llm.is_mock_enabled", return_value=False):
        with patch("quantinsight.agent.llm._call_groq_chat_completion", side_effect=mock_completion):
            with pytest.raises(Exception, match="429"):
                await call_groq("System", "User", api_key="fake")

    # Verify that all 6 fallback candidates were tried
    assert len(attempted_models) == 6
    assert attempted_models[0] == "llama-3.3-70b-versatile"
    assert "llama-3.1-8b-instant" in attempted_models


@pytest.mark.anyio
async def test_depleted_models_resets_on_ttl_or_explicit_reset():
    import time
    from quantinsight.agent.llm import _depleted_models, reset_depleted_models

    reset_depleted_models()
    _depleted_models["llama-3.3-70b-versatile"] = time.time() - 360.0  # Expired > 300s ago

    from quantinsight.agent.llm import call_groq

    async def mock_completion(client, candidate, messages, response_json=True):
        return "OK"

    with patch("quantinsight.agent.llm.is_mock_enabled", return_value=False):
        with patch("quantinsight.agent.llm._call_groq_chat_completion", side_effect=mock_completion):
            await call_groq("System", "User", api_key="fake")

    # Expired model should have been purged from _depleted_models
    assert "llama-3.3-70b-versatile" not in _depleted_models


@pytest.mark.anyio
async def test_agent_handles_all_llm_models_exhausted(temp_chroma, temp_db, mock_ingestion_setup):
    markdown_content = "# Section 1\nProse content."
    mock_ingestion_setup(markdown_content)
    paper_id, _ = await ingest_paper(
        arxiv_id="2303.99992",
        title="Exhaustion Test Paper",
        authors=["Alice"],
        api_key="mock_key",
        groq_api_key="mock_key",
    )

    with patch("quantinsight.agent.nodes.planner.is_mock_enabled", return_value=False):
        with patch("quantinsight.agent.nodes.synthesizer.is_mock_enabled", return_value=False):
            with patch("quantinsight.agent.nodes.verifier.is_mock_enabled", return_value=False):
                with patch("quantinsight.agent.llm.is_mock_enabled", return_value=False):
                    with patch("quantinsight.agent.llm._call_groq_chat_completion", side_effect=Exception("429 Rate limit - tokens per day (TPD)")):
                        response = await run_agent("Test query under API outage", paper_ids=[paper_id])

                        assert response.answer is not None
                        assert "Fallback" in response.answer or "due to API issue" in response.answer
                        assert response.self_correction_applied is False
                        assert "API issue" in response.confidence_note or "Degraded" in response.confidence_note





