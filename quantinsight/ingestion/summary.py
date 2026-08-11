import json
import logging
import os
import re
from datetime import UTC, datetime
from uuid import UUID, uuid4

from dotenv import load_dotenv
from groq import AsyncGroq, GroqError
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from quantinsight.schemas.models import CitedSummary, PaperChunk

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)


def extract_json(text: str) -> dict:
    """
    Extract and parse a JSON object from text, handling markdown code blocks
    or malformed whitespace gracefully.
    """
    text_strip = text.strip()

    # Try direct parse
    try:
        return json.loads(text_strip)
    except json.JSONDecodeError:
        pass

    # Try matching within ```json ... ``` or ``` ... ```
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # Try finding the first '{' and last '}'
    first_bracket = text_strip.find("{")
    last_bracket = text_strip.rfind("}")
    if first_bracket != -1 and last_bracket != -1:
        try:
            return json.loads(text_strip[first_bracket : last_bracket + 1])
        except json.JSONDecodeError:
            pass

    raise ValueError(f"Failed to parse JSON from text response: {text[:200]}...")


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((GroqError, IOError)),
    reraise=True,
)
async def _call_groq_chat_completion(
    client: AsyncGroq, model: str, messages: list[dict]
) -> str:
    """
    Execute chat completion with tenacity retry rules.
    """
    response = await client.chat.completions.create(
        model=model,
        messages=messages,
        response_format={"type": "json_object"},
        temperature=0.2,
    )
    return response.choices[0].message.content


def generate_local_embedding_summary(
    paper_id: UUID, chunks: list[PaperChunk]
) -> CitedSummary:
    """
    Fallback generator using sentence-transformers/all-MiniLM-L6-v2 embeddings
    for local extractive summarization when Groq API is unavailable or rate limited.
    """
    if not chunks:
        return CitedSummary(
            id=uuid4(),
            paper_id=paper_id,
            summary="No chunks available for summary generation.",
            key_claims=[],
            supporting_chunk_ids=[],
            generated_at=datetime.now(UTC),
            model_used="all-MiniLM-L6-v2-fallback",
        )

    try:
        import numpy as np
        from sentence_transformers import SentenceTransformer

        model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
        texts = [c.content for c in chunks]
        chunk_embeddings = model.encode(texts)

        query = "Main contribution, methodology, architecture, and empirical experimental results"
        query_embedding = model.encode(query)

        similarities = np.dot(chunk_embeddings, query_embedding) / (
            np.linalg.norm(chunk_embeddings, axis=1) * np.linalg.norm(query_embedding) + 1e-8
        )

        top_indices = np.argsort(similarities)[::-1][:3]
        top_chunks = [chunks[i] for i in top_indices]

        summary_paragraphs = [
            c.content[:300] + "..." if len(c.content) > 300 else c.content
            for c in top_chunks
        ]
        summary_text = "\n\n".join(summary_paragraphs)
        key_claims = [
            f"Key finding (Page {c.page_number}): {c.content[:150]}..."
            for c in top_chunks
        ]
        supporting_chunk_ids = [c.id for c in top_chunks]

        return CitedSummary(
            id=uuid4(),
            paper_id=paper_id,
            summary=summary_text,
            key_claims=key_claims,
            supporting_chunk_ids=supporting_chunk_ids,
            generated_at=datetime.now(UTC),
            model_used="sentence-transformers/all-MiniLM-L6-v2",
        )
    except Exception as e:
        logger.warning(f"Embedding fallback failed: {e}. Returning basic snippet.")
        first_chunk_text = chunks[0].content[:200] if chunks else ""
        return CitedSummary(
            id=uuid4(),
            paper_id=paper_id,
            summary=f"Extracted paper snippet: {first_chunk_text}",
            key_claims=["Key claim extracted from initial paper chunk."],
            supporting_chunk_ids=[chunks[0].id] if chunks else [],
            generated_at=datetime.now(UTC),
            model_used="all-MiniLM-L6-v2-fallback",
        )


async def generate_cited_summary(
    paper_id: UUID,
    chunks: list[PaperChunk],
    api_key: str | None = None,
    model: str = "llama-3.3-70b-versatile",
) -> CitedSummary:
    """
    Generate a CitedSummary for a given paper by summarizing the text chunks using Groq,
    ensuring all claims reference valid chunk IDs.
    """
    resolved_api_key = api_key or os.environ.get("GROQ_API_KEY")
    if not resolved_api_key or resolved_api_key == "your_groq_key_here" or os.environ.get("MOCK_LLM") == "true":
        logger.warning(
            "Using all-MiniLM-L6-v2 embedding fallback because GROQ_API_KEY is unconfigured or MOCK_LLM is enabled."
        )
        return generate_local_embedding_summary(paper_id, chunks)

    if not chunks:
        raise ValueError("Cannot generate summary for an empty list of chunks")

    # Limit chunk text length to ~28,000 chars (~7,000 tokens) to respect Groq 12,000 TPM limit
    formatted_chunks = []
    current_chars = 0
    max_chars = 28000

    for chunk in chunks:
        chunk_str = f"=== CHUNK ID: {chunk.id} (Page {chunk.page_number}) ===\n{chunk.content}\n\n"
        if current_chars + len(chunk_str) > max_chars:
            if formatted_chunks:
                break
            chunk_str = chunk_str[:max_chars]
        formatted_chunks.append(chunk_str)
        current_chars += len(chunk_str)

    chunks_text = "".join(formatted_chunks)

    system_prompt = (
        "You are a professional research analysis assistant. Analyze the provided paper content "
        "(segmented into chunks with UUID identifiers) and produce a structured summary.\n\n"
        "You MUST respond ONLY with a JSON object containing the following keys:\n"
        "1. 'summary': A detailed, academic 1-3 paragraph summary of the paper's key findings, methodology, and results.\n"
        "2. 'claims': A list of key claims or findings. Each claim must be an object with:\n"
        "   - 'claim': A string describing the claim.\n"
        "   - 'supporting_chunk_ids': A list of UUID strings from the provided chunks that directly support this claim. "
        "Every claim MUST have at least one supporting chunk ID. Do not invent any chunk IDs."
    )

    user_prompt = (
        f"Analyze the following paper content:\n\n{chunks_text}\n\n"
        "Remember, your output must be a single JSON object matching the requested schema. "
        "Ensure all UUIDs in 'supporting_chunk_ids' are exact matches from the provided CHUNK IDs."
    )

    client = AsyncGroq(api_key=resolved_api_key)

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    try:
        raw_response = await _call_groq_chat_completion(client, model, messages)
    except Exception as e:
        err_msg = str(e).lower()
        if "413" in err_msg or "rate_limit" in err_msg or "tokens per minute" in err_msg:
            logger.warning("Groq TPM limit reached for 70b model. Falling back to llama-3.1-8b-instant...")
            try:
                raw_response = await _call_groq_chat_completion(
                    client, "llama-3.1-8b-instant", messages
                )
                model = "llama-3.1-8b-instant"
            except Exception as fallback_err:
                logger.warning(f"LLM fallback failed: {fallback_err}. Using all-MiniLM-L6-v2 embedding fallback.")
                return generate_local_embedding_summary(paper_id, chunks)
        else:
            logger.warning(f"Groq API call failed: {e}. Using all-MiniLM-L6-v2 embedding fallback.")
            return generate_local_embedding_summary(paper_id, chunks)

    try:
        data = extract_json(raw_response)
    except ValueError as e:
        logger.warning(f"Failed to parse Groq response JSON: {e}. Using all-MiniLM-L6-v2 embedding fallback.")
        return generate_local_embedding_summary(paper_id, chunks)

    summary_text = data.get("summary", "").strip()
    claims_data = data.get("claims", [])

    if not summary_text:
        return generate_local_embedding_summary(paper_id, chunks)

    key_claims = []
    supporting_chunk_ids = []

    valid_chunk_ids = {c.id for c in chunks}

    for idx, claim_item in enumerate(claims_data):
        claim_str = claim_item.get("claim", "").strip()
        if not claim_str:
            continue

        cids = claim_item.get("supporting_chunk_ids", [])
        parsed_cids = []
        for cid in cids:
            try:
                val = UUID(cid)
                if val in valid_chunk_ids:
                    parsed_cids.append(val)
            except ValueError:
                continue

        if not parsed_cids:
            parsed_cids.append(chunks[0].id)

        key_claims.append(claim_str)
        supporting_chunk_ids.extend(parsed_cids)

    unique_chunk_ids = list(set(supporting_chunk_ids))

    if not key_claims:
        key_claims.append("General summary of paper findings.")
        unique_chunk_ids = [chunks[0].id]

    return CitedSummary(
        id=uuid4(),
        paper_id=paper_id,
        summary=summary_text,
        key_claims=key_claims,
        supporting_chunk_ids=unique_chunk_ids,
        generated_at=datetime.now(UTC),
        model_used=model,
    )

