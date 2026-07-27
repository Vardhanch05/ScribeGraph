import os
import tempfile
import logging
import asyncio
from typing import Optional
from uuid import UUID, uuid4
import httpx
from dotenv import load_dotenv
from llama_parse import LlamaParse
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)

# Global semaphore to limit LlamaParse concurrency (free-tier cap: 20 req/min)
_parse_semaphore: Optional[asyncio.Semaphore] = None


class ParsingError(Exception):
    """Exception raised for errors during the parsing/fetching process."""
    pass


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((httpx.HTTPError, ParsingError)),
    reraise=True
)
async def fetch_arxiv_pdf(arxiv_id: str) -> bytes:
    """
    Fetch PDF bytes for a given arXiv ID.
    
    Args:
        arxiv_id: The arXiv identifier (e.g., "1706.03762").
        
    Returns:
        bytes: The PDF file content.
    """
    arxiv_id = arxiv_id.strip()
    url = f"https://arxiv.org/pdf/{arxiv_id}"
    
    headers = {
        "User-Agent": "QuantInsight/0.1 (mailto:contact@quantinsight.org)"
    }
    
    async with httpx.AsyncClient(follow_redirects=True) as client:
        try:
            logger.info(f"Fetching PDF from arXiv: {url}")
            response = await client.get(url, headers=headers, timeout=30.0)
            response.raise_for_status()
            return response.content
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error fetching arXiv ID {arxiv_id}: {e}")
            raise ParsingError(f"HTTP error fetching from arXiv: {e.response.status_code}") from e
        except Exception as e:
            logger.error(f"Error fetching arXiv ID {arxiv_id}: {e}")
            raise ParsingError(f"Failed to download PDF from arXiv: {e}") from e


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    reraise=True
)
async def _call_llamaparse(parser: LlamaParse, file_path: str) -> str:
    """
    Helper function to call LlamaParse asynchronously with retry logic.
    """
    try:
        documents = await parser.aload_data(file_path)
        if not documents:
            raise ParsingError("LlamaParse returned no documents.")
        return "\n\n".join([doc.text for doc in documents])
    except Exception as e:
        logger.error(f"LlamaParse call failed: {e}")
        raise ParsingError(f"LlamaParse call failed: {e}") from e


async def parse_pdf(
    arxiv_id: Optional[str] = None,
    pdf_bytes: Optional[bytes] = None,
    api_key: Optional[str] = None,
) -> str:
    """
    Parse a PDF file (either from arXiv ID or raw bytes) using LlamaParse.
    
    Args:
        arxiv_id: Optional arXiv ID to fetch and parse.
        pdf_bytes: Optional raw PDF bytes to parse.
        api_key: Optional LlamaParse API key. Defaults to LLAMA_CLOUD_API_KEY env var.
        
    Returns:
        str: Raw parsed Markdown string.
    """
    if arxiv_id is None and pdf_bytes is None:
        raise ValueError("Either arxiv_id or pdf_bytes must be provided.")
    if arxiv_id is not None and pdf_bytes is not None:
        raise ValueError("Only one of arxiv_id or pdf_bytes can be provided.")
    
    # Resolve API Key
    llama_key = api_key or os.getenv("LLAMA_CLOUD_API_KEY")
    if not llama_key:
        raise ValueError("LLAMA_CLOUD_API_KEY is not set.")
    
    # If arXiv ID is provided, download PDF bytes
    if arxiv_id is not None:
        pdf_bytes = await fetch_arxiv_pdf(arxiv_id)
        
    # Write bytes to a temporary file
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_file:
        tmp_file.write(pdf_bytes)
        tmp_path = tmp_file.name
        
    try:
        # Initialize LlamaParse
        parser = LlamaParse(
            api_key=llama_key,
            result_type="markdown",
        )
        
        # Resolve semaphore in active event loop
        global _parse_semaphore
        if _parse_semaphore is None:
            _parse_semaphore = asyncio.Semaphore(20)
            
        async with _parse_semaphore:
            logger.info("Acquired LlamaParse semaphore slot. Calling API...")
            markdown_content = await _call_llamaparse(parser, tmp_path)
            # Short sleep to prevent hitting rate limits during sequential calls
            await asyncio.sleep(3.0)
            
        return markdown_content
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass

