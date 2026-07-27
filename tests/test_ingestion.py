import os
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from quantinsight.ingestion.parser import parse_pdf, fetch_arxiv_pdf, ParsingError

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

