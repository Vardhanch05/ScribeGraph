import asyncio
import json
import logging
import os
import tempfile
import time
from uuid import UUID, uuid4

import httpx
from dotenv import load_dotenv
from llama_parse import LlamaParse
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)

# Global semaphore to limit LlamaParse concurrency (free-tier cap: 20 req/min)
_parse_semaphore: asyncio.Semaphore | None = None

WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
ARTIFACTS_DIR = os.path.join(WORKSPACE_ROOT, "artifacts")
CACHE_FILE = os.path.join(ARTIFACTS_DIR, "cache.json")


def _load_cache() -> dict:
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def _save_cache(cache: dict) -> None:
    os.makedirs(ARTIFACTS_DIR, exist_ok=True)
    try:
        with open(CACHE_FILE, "w") as f:
            json.dump(cache, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to write to cache.json: {e}")


class ParsingError(Exception):
    """Exception raised for errors during the parsing/fetching process."""


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((httpx.HTTPError, ParsingError)),
    reraise=True,
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

    headers = {"User-Agent": "QuantInsight/0.1 (mailto:contact@quantinsight.org)"}

    async with httpx.AsyncClient(follow_redirects=True) as client:
        try:
            logger.info(f"Fetching PDF from arXiv: {url}")
            response = await client.get(url, headers=headers, timeout=30.0)
            response.raise_for_status()
            return response.content
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error fetching arXiv ID {arxiv_id}: {e}")
            raise ParsingError(
                f"HTTP error fetching from arXiv: {e.response.status_code}"
            ) from e
        except Exception as e:
            logger.error(f"Error fetching arXiv ID {arxiv_id}: {e}")
            raise ParsingError(f"Failed to download PDF from arXiv: {e}") from e


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    reraise=True,
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
    arxiv_id: str | None = None,
    pdf_bytes: bytes | None = None,
    paper_id: UUID | None = None,
    api_key: str | None = None,
) -> str:
    """
    Parse a PDF file (either from arXiv ID or raw bytes) using LlamaParse.

    Args:
        arxiv_id: Optional arXiv ID to fetch and parse.
        pdf_bytes: Optional raw PDF bytes to parse.
        paper_id: Optional UUID associated with the paper.
        api_key: Optional LlamaParse API key. Defaults to LLAMA_CLOUD_API_KEY env var.

    Returns:
        str: Raw parsed Markdown string.
    """
    if arxiv_id is None and pdf_bytes is None:
        raise ValueError("Either arxiv_id or pdf_bytes must be provided.")
    if arxiv_id is not None and pdf_bytes is not None:
        raise ValueError("Only one of arxiv_id or pdf_bytes can be provided.")

    current_paper_id = paper_id or uuid4()

    # 48h Cache Avoidance Check
    cache = _load_cache()
    cached_paper_id = None

    if paper_id is not None:
        cached_paper_id = paper_id
    elif arxiv_id is not None:
        arxiv_key = f"arxiv_{arxiv_id.strip()}"
        if arxiv_key in cache:
            entry = cache[arxiv_key]
            if time.time() - entry.get("timestamp", 0) < 48 * 3600:
                cached_paper_id = UUID(entry["paper_id"])

    if cached_paper_id is not None:
        cached_file_path = os.path.join(ARTIFACTS_DIR, str(cached_paper_id), "raw.md")
        if os.path.exists(cached_file_path):
            try:
                # Double check that the file is less than 48 hours old on disk
                mtime = os.path.getmtime(cached_file_path)
                if time.time() - mtime < 48 * 3600:
                    logger.info(
                        f"Cache hit! Loading parsed Markdown from {cached_file_path}"
                    )
                    with open(cached_file_path, "r", encoding="utf-8") as f:
                        return f.read()
            except Exception as e:
                logger.warning(
                    f"Failed to read from cache file {cached_file_path}: {e}"
                )

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

        # Persist raw markdown to artifact store
        paper_artifacts_dir = os.path.join(ARTIFACTS_DIR, str(current_paper_id))
        os.makedirs(paper_artifacts_dir, exist_ok=True)
        markdown_file_path = os.path.join(paper_artifacts_dir, "raw.md")
        try:
            with open(markdown_file_path, "w", encoding="utf-8") as f:
                f.write(markdown_content)
            logger.info(f"Persisted raw Markdown to {markdown_file_path}")
        except Exception as e:
            logger.error(f"Failed to persist raw Markdown to {markdown_file_path}: {e}")

        # Update cache mapping if arxiv_id is present
        if arxiv_id is not None:
            arxiv_key = f"arxiv_{arxiv_id.strip()}"
            cache[arxiv_key] = {
                "paper_id": str(current_paper_id),
                "timestamp": time.time(),
            }
            _save_cache(cache)

        return markdown_content
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
