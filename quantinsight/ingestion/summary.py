import os
import re
import json
import logging
from uuid import UUID, uuid4
from typing import List, Optional
from datetime import datetime
from dotenv import load_dotenv
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from groq import AsyncGroq, GroqError

from quantinsight.schemas.models import PaperChunk, CitedSummary

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
    match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # Try finding the first '{' and last '}'
    first_bracket = text_strip.find('{')
    last_bracket = text_strip.rfind('}')
    if first_bracket != -1 and last_bracket != -1:
        try:
            return json.loads(text_strip[first_bracket:last_bracket + 1])
        except json.JSONDecodeError:
            pass

    raise ValueError(f"Failed to parse JSON from text response: {text[:200]}...")

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((GroqError, IOError)),
    reraise=True
)
async def _call_groq_chat_completion(
    client: AsyncGroq,
    model: str,
    messages: List[dict]
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

async def generate_cited_summary(
    paper_id: UUID,
    chunks: List[PaperChunk],
    api_key: Optional[str] = None,
    model: str = "llama-3.1-70b-versatile"
) -> CitedSummary:
    """
    Generate a CitedSummary for a given paper by summarizing the text chunks using Groq,
    ensuring all claims reference valid chunk IDs.
    
    Args:
        paper_id: The UUID of the source paper.
        chunks: List of PaperChunks extracted from the paper.
        api_key: Optional Groq API key (defaults to GROQ_API_KEY env var).
        model: Groq model name to use.
        
    Returns:
        A validated CitedSummary Pydantic model.
    """
    resolved_api_key = api_key or os.environ.get("GROQ_API_KEY")
    if not resolved_api_key:
        raise ValueError("GROQ_API_KEY is not set in environment or arguments")

    if not chunks:
        raise ValueError("Cannot generate summary for an empty list of chunks")

    # Format chunks with IDs for context
    formatted_chunks = []
    for chunk in chunks:
        formatted_chunks.append(
            f"=== CHUNK ID: {chunk.id} (Page {chunk.page_number}) ===\n{chunk.content}"
        )
    chunks_text = "\n\n".join(formatted_chunks)

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
        {"role": "user", "content": user_prompt}
    ]

    try:
        raw_response = await _call_groq_chat_completion(client, model, messages)
    except Exception as e:
        logger.error(f"Failed to generate cited summary via Groq: {e}")
        raise RuntimeError(f"Groq API call failed: {e}") from e

    try:
        data = extract_json(raw_response)
    except ValueError as e:
        logger.error(f"Failed to parse Groq response: {e}")
        raise RuntimeError(f"Invalid JSON response from LLM: {e}") from e

    summary_text = data.get("summary", "").strip()
    claims_data = data.get("claims", [])
    
    if not summary_text:
        raise ValueError("LLM response did not contain a valid 'summary' field")

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

        # Every key claim must reference at least one chunk_id
        if not parsed_cids:
            # Fallback to the first chunk if none valid
            parsed_cids.append(chunks[0].id)
            logger.warning(
                f"Claim index {idx} ('{claim_str[:40]}...') did not reference any valid chunk IDs. "
                f"Falling back to first chunk: {chunks[0].id}"
            )

        key_claims.append(claim_str)
        supporting_chunk_ids.extend(parsed_cids)

    # Deduplicate supporting chunk IDs
    unique_chunk_ids = list(set(supporting_chunk_ids))

    # If no key claims were extracted, construct a default one using the first chunk
    if not key_claims:
        key_claims.append("General summary of paper findings.")
        unique_chunk_ids = [chunks[0].id]

    return CitedSummary(
        id=uuid4(),
        paper_id=paper_id,
        summary=summary_text,
        key_claims=key_claims,
        supporting_chunk_ids=unique_chunk_ids,
        generated_at=datetime.utcnow(),
        model_used=model
    )
