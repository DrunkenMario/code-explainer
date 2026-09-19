"""Core logic for the plain-English Python explainer."""

from .parser import Block, split_blocks
from .llm import LLMError, explain_blocks, explain_overview

__all__ = [
    "Block",
    "split_blocks",
    "explain_overview",
    "explain_blocks",
    "LLMError",
]
