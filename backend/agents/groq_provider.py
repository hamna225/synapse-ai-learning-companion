"""Groq chat model factory for resume analysis and document topic extraction."""
import os

from dotenv import load_dotenv

load_dotenv()


def get_groq_text_model(temperature=0, max_tokens=4096, json_mode=False):
    from langchain_openai import ChatOpenAI

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY is not configured in the backend environment.")

    options = {
        "model": os.getenv("GROQ_RESUME_MODEL", "openai/gpt-oss-120b"),
        "api_key": api_key,
        "base_url": "https://api.groq.com/openai/v1",
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if json_mode:
        options["model_kwargs"] = {"response_format": {"type": "json_object"}}
    return ChatOpenAI(**options)
