import os
import re
import time

import httpx

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"

# Model ID as listed in Groq console — override via GROQ_MODEL env var
LLM_MODEL_ID = os.environ.get("GROQ_MODEL", "qwen-qwen3-32b")

_api_key: str = None


def load():
    """Read GROQ_API_KEY from environment. Must be set before starting the service."""
    global _api_key
    _api_key = os.environ.get("GROQ_API_KEY", "")
    if not _api_key:
        raise RuntimeError(
            "GROQ_API_KEY environment variable is not set. "
            "Set it before starting the service: export GROQ_API_KEY=gsk_..."
        )


def generate_reply(messages: list, max_new_tokens: int = 200) -> str:
    """Send a chat request to Groq and return the assistant reply text."""
    if not _api_key:
        raise RuntimeError("LLM not loaded. Call llm.load() at startup.")

    for attempt in range(4):
        response = httpx.post(
            GROQ_API_URL,
            headers={
                "Authorization": f"Bearer {_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": LLM_MODEL_ID,
                "messages": messages,
                "max_tokens": max_new_tokens,
                "temperature": 0,
            },
            timeout=60.0,
        )
        if response.status_code == 429:
            retry_after = float(response.headers.get("retry-after", 2 ** (attempt + 1)))
            time.sleep(retry_after)
            continue
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        # Qwen3 on Groq returns <think>...</think> before the actual reply — strip it.
        content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()
        return content

    raise RuntimeError("Groq API rate limit exceeded after 4 retries.")


def is_loaded() -> bool:
    return bool(_api_key)
