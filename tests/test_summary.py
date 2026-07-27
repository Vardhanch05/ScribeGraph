from unittest.mock import patch
from uuid import uuid4

import pytest

from quantinsight.ingestion.summary import extract_json, generate_cited_summary
from quantinsight.schemas.models import ChunkType, CitedSummary, PaperChunk


def test_extract_json():
    # Direct JSON
    assert extract_json('{"key": "value"}') == {"key": "value"}
    # JSON with spaces and newlines
    assert extract_json('\n  {"key": "value"} \n') == {"key": "value"}
    # Codeblock JSON
    assert extract_json('```json\n{"key": "value"}\n```') == {"key": "value"}
    # Codeblock JSON without language
    assert extract_json('```\n{"key": "value"}\n```') == {"key": "value"}
    # Leading text then JSON
    assert extract_json('Here is the json: {"key": "value"}') == {"key": "value"}
    
    with pytest.raises(ValueError):
        extract_json("not json")

@pytest.mark.anyio
@patch("quantinsight.ingestion.summary._call_groq_chat_completion")
async def test_generate_cited_summary_success(mock_call_groq):
    paper_id = uuid4()
    chunk1 = PaperChunk(
        id=uuid4(),
        paper_id=paper_id,
        chunk_type=ChunkType.PROSE,
        content="This is the first chunk content.",
        page_number=1,
        order_index=0
    )
    chunk2 = PaperChunk(
        id=uuid4(),
        paper_id=paper_id,
        chunk_type=ChunkType.PROSE,
        content="This is the second chunk content.",
        page_number=2,
        order_index=1
    )
    
    # Mock LLM response
    mock_response = f"""
    {{
        "summary": "This is a great summary of the paper.",
        "claims": [
            {{
                "claim": "Claim 1 supported by chunk 1",
                "supporting_chunk_ids": ["{chunk1.id}"]
            }},
            {{
                "claim": "Claim 2 supported by both chunks",
                "supporting_chunk_ids": ["{chunk1.id}", "{chunk2.id}"]
            }}
        ]
    }}
    """
    mock_call_groq.return_value = mock_response
    
    summary = await generate_cited_summary(
        paper_id=paper_id,
        chunks=[chunk1, chunk2],
        api_key="mock_key"
    )
    
    assert isinstance(summary, CitedSummary)
    assert summary.paper_id == paper_id
    assert summary.summary == "This is a great summary of the paper."
    assert summary.key_claims == [
        "Claim 1 supported by chunk 1",
        "Claim 2 supported by both chunks"
    ]
    # Verify both chunk IDs are present and deduplicated
    assert set(summary.supporting_chunk_ids) == {chunk1.id, chunk2.id}
    assert summary.model_used == "llama-3.1-70b-versatile"

@pytest.mark.anyio
@patch("quantinsight.ingestion.summary._call_groq_chat_completion")
async def test_generate_cited_summary_fallback_on_invalid_citations(mock_call_groq):
    paper_id = uuid4()
    chunk1 = PaperChunk(
        id=uuid4(),
        paper_id=paper_id,
        chunk_type=ChunkType.PROSE,
        content="First chunk.",
        page_number=1,
        order_index=0
    )
    
    # Mock response returning hallucinated chunk ID
    hallucinated_id = uuid4()
    mock_response = f"""
    {{
        "summary": "Summary.",
        "claims": [
            {{
                "claim": "Claim with fake ID",
                "supporting_chunk_ids": ["{hallucinated_id}", "not-a-uuid"]
            }}
        ]
    }}
    """
    mock_call_groq.return_value = mock_response
    
    summary = await generate_cited_summary(
        paper_id=paper_id,
        chunks=[chunk1],
        api_key="mock_key"
    )
    
    # Must fallback to the only valid chunk (chunk1.id)
    assert summary.supporting_chunk_ids == [chunk1.id]

@pytest.mark.anyio
@patch("quantinsight.ingestion.summary._call_groq_chat_completion")
async def test_generate_cited_summary_invalid_json(mock_call_groq):
    paper_id = uuid4()
    chunk1 = PaperChunk(
        id=uuid4(),
        paper_id=paper_id,
        chunk_type=ChunkType.PROSE,
        content="Content.",
        page_number=1,
        order_index=0
    )
    
    mock_call_groq.return_value = "invalid json from LLM"
    
    with pytest.raises(RuntimeError, match="Invalid JSON response from LLM"):
        await generate_cited_summary(
            paper_id=paper_id,
            chunks=[chunk1],
            api_key="mock_key"
        )
