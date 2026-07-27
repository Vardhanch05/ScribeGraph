import os
import pytest
import json
import time
from uuid import UUID, uuid4
from unittest.mock import AsyncMock, patch, MagicMock
from quantinsight.ingestion.parser import parse_pdf, fetch_arxiv_pdf, ParsingError

@pytest.fixture(autouse=True)
def mock_parser_artifacts(tmp_path):
    test_artifacts_dir = str(tmp_path / "artifacts")
    test_cache_file = os.path.join(test_artifacts_dir, "cache.json")
    with patch("quantinsight.ingestion.parser.ARTIFACTS_DIR", test_artifacts_dir), \
         patch("quantinsight.ingestion.parser.CACHE_FILE", test_cache_file):
        yield

@pytest.mark.anyio
async def test_parse_pdf_argument_validation():
    # Both inputs provided
    with pytest.raises(ValueError, match="Only one of arxiv_id or pdf_bytes can be provided"):
        await parse_pdf(arxiv_id="1234.5678", pdf_bytes=b"fake pdf")

    # Neither input provided
    with pytest.raises(ValueError, match="Either arxiv_id or pdf_bytes must be provided"):
        await parse_pdf()

@pytest.mark.anyio
async def test_parse_pdf_missing_api_key():
    # Clear both arguments and environment to test missing key
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(ValueError, match="LLAMA_CLOUD_API_KEY is not set"):
            await parse_pdf(pdf_bytes=b"fake pdf")

@pytest.mark.anyio
@patch("quantinsight.ingestion.parser.LlamaParse")
async def test_parse_pdf_bytes_success(mock_llama_parse):
    # Setup mocks
    mock_parser_instance = MagicMock()
    mock_parser_instance.aload_data = AsyncMock(return_value=[
        MagicMock(text="Parsed header"),
        MagicMock(text="Parsed body content")
    ])
    mock_llama_parse.return_value = mock_parser_instance
    
    # Call with pdf_bytes
    result = await parse_pdf(pdf_bytes=b"fake pdf content", api_key="fake_key")
    
    assert "Parsed header" in result
    assert "Parsed body content" in result
    mock_llama_parse.assert_called_once_with(api_key="fake_key", result_type="markdown")
    mock_parser_instance.aload_data.assert_called_once()

@pytest.mark.anyio
@patch("quantinsight.ingestion.parser.fetch_arxiv_pdf")
@patch("quantinsight.ingestion.parser.LlamaParse")
async def test_parse_pdf_arxiv_id_success(mock_llama_parse, mock_fetch_arxiv):
    # Setup mocks
    mock_fetch_arxiv.return_value = b"downloaded pdf content"
    mock_parser_instance = MagicMock()
    mock_parser_instance.aload_data = AsyncMock(return_value=[
        MagicMock(text="Arxiv content")
    ])
    mock_llama_parse.return_value = mock_parser_instance
    
    # Call with arxiv_id
    result = await parse_pdf(arxiv_id="1706.03762", api_key="fake_key")
    
    assert result == "Arxiv content"
    mock_fetch_arxiv.assert_called_once_with("1706.03762")
    mock_llama_parse.assert_called_once_with(api_key="fake_key", result_type="markdown")
    mock_parser_instance.aload_data.assert_called_once()

@pytest.mark.anyio
@patch("quantinsight.ingestion.parser.asyncio.sleep")
@patch("quantinsight.ingestion.parser.LlamaParse")
async def test_parse_pdf_rate_limiter(mock_llama_parse, mock_sleep):
    # Setup mocks
    mock_parser_instance = MagicMock()
    mock_parser_instance.aload_data = AsyncMock(return_value=[
        MagicMock(text="Content")
    ])
    mock_llama_parse.return_value = mock_parser_instance
    
    # Call parse_pdf
    await parse_pdf(pdf_bytes=b"fake pdf", api_key="fake_key")
    
    # Verify sleep was called to rate limit
    mock_sleep.assert_called_once_with(3.0)

@pytest.mark.anyio
@patch("quantinsight.ingestion.parser.LlamaParse")
async def test_parse_pdf_artifact_persistence_and_caching(mock_llama_parse):
    # Setup mock parser response
    mock_parser_instance = MagicMock()
    mock_parser_instance.aload_data = AsyncMock(return_value=[
        MagicMock(text="Freshly parsed text")
    ])
    mock_llama_parse.return_value = mock_parser_instance
    
    paper_id = uuid4()
    
    # Import ARTIFACTS_DIR dynamically to check file path
    from quantinsight.ingestion.parser import ARTIFACTS_DIR
    
    # 1. First parse: Cache miss
    result = await parse_pdf(pdf_bytes=b"pdf content", paper_id=paper_id, api_key="fake")
    assert result == "Freshly parsed text"
    mock_parser_instance.aload_data.assert_called_once()
    
    # Check that file was written
    expected_path = os.path.join(ARTIFACTS_DIR, str(paper_id), "raw.md")
    assert os.path.exists(expected_path)
    with open(expected_path, "r", encoding="utf-8") as f:
        assert f.read() == "Freshly parsed text"
        
    # 2. Second parse with same paper_id: Cache hit (aload_data should NOT be called again)
    mock_parser_instance.aload_data.reset_mock()
    result2 = await parse_pdf(pdf_bytes=b"pdf content", paper_id=paper_id, api_key="fake")
    assert result2 == "Freshly parsed text"
    mock_parser_instance.aload_data.assert_not_called()

@pytest.mark.anyio
@patch("quantinsight.ingestion.parser.fetch_arxiv_pdf")
@patch("quantinsight.ingestion.parser.LlamaParse")
async def test_parse_pdf_arxiv_caching_and_expiration(mock_llama_parse, mock_fetch_arxiv):
    mock_fetch_arxiv.return_value = b"downloaded pdf content"
    
    # Import ARTIFACTS_DIR and CACHE_FILE dynamically
    from quantinsight.ingestion.parser import ARTIFACTS_DIR, CACHE_FILE
    
    mock_parser_instance = MagicMock()
    mock_parser_instance.aload_data = AsyncMock(return_value=[
        MagicMock(text="Arxiv cached text")
    ])
    mock_llama_parse.return_value = mock_parser_instance
    
    # Parse by arxiv_id first
    arxiv_id = "2303.12345"
    result = await parse_pdf(arxiv_id=arxiv_id, api_key="fake")
    assert result == "Arxiv cached text"
    mock_parser_instance.aload_data.assert_called_once()
    mock_fetch_arxiv.assert_called_once_with(arxiv_id)
    
    # Second parse should hit the cache
    mock_parser_instance.aload_data.reset_mock()
    mock_fetch_arxiv.reset_mock()
    result2 = await parse_pdf(arxiv_id=arxiv_id, api_key="fake")
    assert result2 == "Arxiv cached text"
    mock_parser_instance.aload_data.assert_not_called()
    mock_fetch_arxiv.assert_not_called()
    
    # Force cache expiration by modifying modification time to 50 hours ago
    with open(CACHE_FILE, "r") as f:
        cache_data = json.load(f)
    cached_paper_id = cache_data[f"arxiv_{arxiv_id}"]["paper_id"]
    
    cached_file_path = os.path.join(ARTIFACTS_DIR, cached_paper_id, "raw.md")
    past_time = time.time() - (50 * 3600)
    os.utime(cached_file_path, (past_time, past_time))
    
    # Also update the cache.json timestamp to 50 hours ago
    cache_data[f"arxiv_{arxiv_id}"]["timestamp"] = past_time
    with open(CACHE_FILE, "w") as f:
        json.dump(cache_data, f)
        
    # Third parse: should be cache expiration, calling aload_data again
    mock_parser_instance.aload_data.reset_mock()
    mock_fetch_arxiv.reset_mock()
    mock_parser_instance.aload_data.return_value = [MagicMock(text="New text post expiration")]
    
    result3 = await parse_pdf(arxiv_id=arxiv_id, api_key="fake")
    assert result3 == "New text post expiration"
    mock_parser_instance.aload_data.assert_called_once()
    mock_fetch_arxiv.assert_called_once_with(arxiv_id)




