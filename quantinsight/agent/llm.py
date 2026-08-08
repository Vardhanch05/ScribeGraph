import json
import logging
import os
import re
from typing import Any, Optional

from groq import AsyncGroq, GroqError
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

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
    client: AsyncGroq, model: str, messages: list[dict], response_json: bool
) -> str:
    """
    Execute chat completion with tenacity retry rules.
    """
    kwargs = {
        "model": model,
        "messages": messages,
        "temperature": 0.2,
    }
    if response_json:
        kwargs["response_format"] = {"type": "json_object"}

    response = await client.chat.completions.create(**kwargs)
    return response.choices[0].message.content


def is_mock_enabled(api_key: Optional[str] = None) -> bool:
    """Check if LLM is mocked."""
    resolved_api_key = api_key or os.environ.get("GROQ_API_KEY")
    return (
        not resolved_api_key
        or resolved_api_key == "your_groq_key_here"
        or os.environ.get("MOCK_LLM") == "true"
    )


async def call_groq(
    system_prompt: str,
    user_prompt: str,
    model: str = "llama-3.3-70b-versatile",
    api_key: Optional[str] = None,
    response_json: bool = True,
) -> str:
    """
    Call Groq API with system and user prompts, retrying on errors.
    """
    resolved_api_key = api_key or os.environ.get("GROQ_API_KEY")
    if is_mock_enabled(resolved_api_key):
        raise ValueError("Mock LLM mode is active. Do not call this function directly.")

    client = AsyncGroq(api_key=resolved_api_key)
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    return await _call_groq_chat_completion(
        client, model, messages, response_json=response_json
    )
