import asyncio
import json
import logging
import os
import re
from typing import Any, Optional

from groq import AsyncGroq, GroqError
from tenacity import (
    retry,
    retry_if_exception,
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


def _should_retry_exception(e: Exception) -> bool:
    if isinstance(e, GroqError):
        err_msg = str(e).lower()
        if "tokens per day" in err_msg or "tpd" in err_msg:
            return False
        return True
    return isinstance(e, IOError)



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


import time

_depleted_models: dict[str, float] = {}
DEPLETION_TTL_SECONDS = 300.0


def reset_depleted_models() -> None:
    """Reset all depleted model markers."""
    global _depleted_models
    _depleted_models.clear()


def parse_retry_after(msg: str) -> float:
    match = re.search(r"try again in (?:(\d+)m)?([\d\.]+)s", msg)
    if match:
        mins = float(match.group(1)) if match.group(1) else 0.0
        secs = float(match.group(2))
        return mins * 60.0 + secs + 1.0
    return 5.0


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
    global _depleted_models
    resolved_api_key = api_key or os.environ.get("GROQ_API_KEY")
    if is_mock_enabled(resolved_api_key):
        raise ValueError("Mock LLM mode is active. Do not call this function directly.")

    client = AsyncGroq(api_key=resolved_api_key, timeout=60.0)
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    all_candidates = [
        model,
        "llama-3.1-8b-instant",
        "openai/gpt-oss-120b",
        "openai/gpt-oss-20b",
        "qwen/qwen3.6-27b",
        "allam-2-7b",
    ]

    now = time.time()
    expired = [m for m, ts in _depleted_models.items() if now - ts > DEPLETION_TTL_SECONDS]
    for m in expired:
        _depleted_models.pop(m, None)

    fallback_models = []
    for m in all_candidates:
        if m not in fallback_models and m not in _depleted_models:
            fallback_models.append(m)

    if not fallback_models:
        _depleted_models.clear()
        fallback_models = list(dict.fromkeys(all_candidates))

    last_exception = None

    for candidate in fallback_models:
        try:
            return await _call_groq_chat_completion(
                client, candidate, messages, response_json=response_json
            )
        except Exception as e:
            err_msg = str(e).lower()
            if "429" in err_msg or "413" in err_msg or "rate limit" in err_msg or "limit" in err_msg:
                is_tpd = "tpd" in err_msg or "tokens per day" in err_msg
                is_context_limit = "413" in err_msg or "request too large" in err_msg
                if is_tpd or is_context_limit:
                    logger.warning(f"Groq model '{candidate}' TPD/Context limit reached ({e}). Moving to next model.")
                    _depleted_models[candidate] = time.time()
                    last_exception = e
                    continue

                sleep_time = parse_retry_after(err_msg)
                logger.warning(
                    f"Groq model '{candidate}' hit rate limit ({e}). Retrying after {sleep_time:.2f}s..."
                )
                last_exception = e
                await asyncio.sleep(sleep_time)

                if len(_depleted_models) >= len(all_candidates):
                    _depleted_models.clear()

                for attempt in range(3):
                    try:
                        return await _call_groq_chat_completion(
                            client, candidate, messages, response_json=response_json
                        )
                    except Exception as sub_e:
                        sub_msg = str(sub_e).lower()
                        if "tpd" in sub_msg or "tokens per day" in sub_msg or "413" in sub_msg or "request too large" in sub_msg:
                            _depleted_models[candidate] = time.time()
                            break
                        sub_sleep = parse_retry_after(sub_msg)
                        logger.warning(f"Retry attempt {attempt+1} hit limit on '{candidate}'. Sleeping {sub_sleep:.2f}s...")
                        last_exception = sub_e
                        await asyncio.sleep(sub_sleep)
                continue
            raise

    raise last_exception or RuntimeError("All Groq model fallbacks exhausted due to rate limits.")

