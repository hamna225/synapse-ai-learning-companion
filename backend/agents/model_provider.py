"""Shared xAI text-model selection for tutor and assessment generation."""

import os

from dotenv import load_dotenv

load_dotenv()


def get_text_model(temperature=0, max_tokens=4096, reasoning_effort=None):
    """Create the configured Grok chat model using xAI's OpenAI-compatible API."""
    from langchain_openai import ChatOpenAI

    api_key = os.getenv("XAI_API_KEY")
    if not api_key:
        raise ValueError("XAI_API_KEY is not configured.")

    model_options = {
        "model": os.getenv("GROK_TEXT_MODEL", "grok-4.7"),
        "api_key": api_key,
        "base_url": "https://api.x.ai/v1",
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if reasoning_effort:
        model_options["reasoning_effort"] = reasoning_effort
    return ChatOpenAI(**model_options)
