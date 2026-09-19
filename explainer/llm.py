"""Thin wrapper around the Anthropic Messages API.

Everything the UI needs is here: two calls (overview, per-block), JSON parsing
that survives a chatty model, and batching so a long file does not blow past
the output token limit in one request.
"""

from __future__ import annotations

import json
import os
import re
from typing import Dict, List, Optional

from anthropic import Anthropic, APIError

from .parser import Block, blocks_to_prompt
from .prompts import (
    AUDIENCE_PROFILES,
    BLOCKS_USER_TEMPLATE,
    OVERVIEW_USER_TEMPLATE,
    SYSTEM_PROMPT,
)

DEFAULT_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5")
BATCH_SIZE = 10  # blocks per request


class LLMError(RuntimeError):
    """Anything that stops us returning an explanation."""


def get_client(api_key: Optional[str] = None) -> Anthropic:
    key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise LLMError(
            "No API key found. Add ANTHROPIC_API_KEY to your .env file, "
            "or paste a key in the sidebar."
        )
    return Anthropic(api_key=key)


def _parse_json(text: str) -> dict:
    text = text.strip()
    text = re.sub(r"^```(?:json)?", "", text).strip()
    text = re.sub(r"```$", "", text).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Truncated or trailing-prose output: keep up to the last closing brace.
    last = text.rfind("}")
    if last != -1:
        try:
            return json.loads(text[: last + 1])
        except json.JSONDecodeError:
            pass
    raise LLMError("The model did not return usable JSON. Try again.")


def _json_call(
    client: Anthropic,
    model: str,
    audience: str,
    user_prompt: str,
    max_tokens: int = 4096,
) -> dict:
    system = SYSTEM_PROMPT.format(
        audience=AUDIENCE_PROFILES.get(audience, AUDIENCE_PROFILES["Absolute beginner"])
    )
    try:
        response = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system,
            messages=[
                {"role": "user", "content": user_prompt},
                # Prefilling "{" forces the reply to start as JSON.
                {"role": "assistant", "content": "{"},
            ],
        )
    except APIError as exc:  # network, auth, rate limit, bad model name
        raise LLMError(f"Anthropic API error: {exc}") from exc

    body = "".join(part.text for part in response.content if part.type == "text")
    return _parse_json("{" + body)


def explain_overview(
    code: str,
    audience: str = "Absolute beginner",
    model: str = DEFAULT_MODEL,
    api_key: Optional[str] = None,
) -> dict:
    """Big-picture summary + connection map for the whole file."""
    client = get_client(api_key)
    data = _json_call(
        client,
        model,
        audience,
        OVERVIEW_USER_TEMPLATE.format(code=code),
        max_tokens=3000,
    )
    data.setdefault("headline", "")
    data.setdefault("analogy", "")
    data.setdefault("what_it_does", [])
    data.setdefault("inputs_outputs", "")
    data.setdefault("connections", [])
    data.setdefault("key_terms", [])
    return data


def explain_blocks(
    code: str,
    blocks: List[Block],
    audience: str = "Absolute beginner",
    model: str = DEFAULT_MODEL,
    api_key: Optional[str] = None,
    progress_callback=None,
) -> Dict[int, dict]:
    """Explain every block. Returns {block_id: {title, explanation, connects_to}}."""
    client = get_client(api_key)
    results: Dict[int, dict] = {}
    batches = [blocks[i : i + BATCH_SIZE] for i in range(0, len(blocks), BATCH_SIZE)]

    for index, batch in enumerate(batches, start=1):
        data = _json_call(
            client,
            model,
            audience,
            BLOCKS_USER_TEMPLATE.format(code=code, blocks=blocks_to_prompt(batch)),
            max_tokens=4096,
        )
        for item in data.get("explanations", []):
            try:
                block_id = int(item["id"])
            except (KeyError, TypeError, ValueError):
                continue
            results[block_id] = {
                "title": item.get("title", ""),
                "explanation": item.get("explanation", ""),
                "connects_to": item.get("connects_to", ""),
            }
        if progress_callback:
            progress_callback(index, len(batches))

    # Never leave a chunk visibly empty in the UI.
    for block in blocks:
        results.setdefault(
            block.id,
            {
                "title": "Explanation unavailable",
                "explanation": "This chunk could not be explained. Try running it again.",
                "connects_to": "",
            },
        )
    return results
