"""Vision helper for describing figures during material ingestion."""

import hashlib
import base64
from io import BytesIO
import os
from pathlib import Path
import re
import threading
import time

from dotenv import load_dotenv
from PIL import Image


load_dotenv()
_client = None
_client_lock = threading.Lock()
_vision_request_lock = threading.Lock()
_vision_unavailable_until = 0


def _create_vision_client(api_key):
    from openai import OpenAI

    return OpenAI(
        api_key=api_key,
        base_url="https://api.x.ai/v1",
        timeout=45,
    )


def _visual_cache_file(image_bytes, source_location, surrounding_text, model):
    cache_dir = Path(os.getenv("SYNAPSE_VISUAL_CACHE_DIR", "data/visual_cache"))
    cache_key = hashlib.sha256(
        b"synapse-visual-v2\0xai\0"
        + model.encode("utf-8")
        + b"\0"
        + source_location.encode("utf-8")
        + b"\0"
        + surrounding_text[:1200].encode("utf-8")
        + b"\0"
        + image_bytes
    ).hexdigest()
    return cache_dir / f"{cache_key}.txt"


def describe_visual(image_bytes, source_location, surrounding_text=""):
    """Return a concise, source-local description, or empty text on failure."""
    global _client, _vision_unavailable_until

    api_key = os.getenv("XAI_API_KEY")
    if not api_key:
        print("Visual extraction skipped: XAI_API_KEY is not configured.")
        return ""

    try:
        model = os.getenv("GROK_VISION_MODEL", "grok-4.7")
        cache_file = _visual_cache_file(
            image_bytes, source_location, surrounding_text, model
        )
        try:
            cached_description = cache_file.read_text(encoding="utf-8").strip()
            if cached_description:
                return cached_description
        except OSError:
            pass

        image = Image.open(BytesIO(image_bytes)).convert("RGB")
        image.thumbnail((1280, 1280))
        image_buffer = BytesIO()
        image.save(image_buffer, format="JPEG", quality=82, optimize=True)
        if _client is None:
            with _client_lock:
                if _client is None:
                    _client = _create_vision_client(api_key)

        prompt = (
            f"Analyze this figure from {source_location}. "
            f"Nearby course text: {surrounding_text[:1200]}\n"
            "Describe only information visibly supported by the image. "
            "Capture diagram parts and relationships, flow direction, "
            "chart axes/trends, and legible labels. Do not guess at "
            "unclear details. Do not infer an icon's intended meaning "
            "from nearby text; describe the icon literally unless the "
            "image labels or connects it to a concept. Return a concise "
            "description under 140 words."
        )
        encoded_image = base64.b64encode(image_buffer.getvalue()).decode("ascii")
        with _vision_request_lock:
            if time.monotonic() < _vision_unavailable_until:
                return ""

            for attempt in range(5):
                try:
                    response = _client.responses.create(
                        model=model,
                        input=[{
                            "role": "user",
                            "content": [
                                {
                                    "type": "input_image",
                                    "image_url": f"data:image/jpeg;base64,{encoded_image}",
                                    "detail": "high",
                                },
                                {"type": "input_text", "text": prompt},
                            ],
                        }],
                        max_output_tokens=220,
                    )
                    break
                except Exception as error:
                    error_text = str(error)
                    is_service_unavailable = (
                        "503" in error_text
                        or "unavailable" in error_text.casefold()
                    )
                    if is_service_unavailable:
                        _vision_unavailable_until = time.monotonic() + 60
                        print(
                            "Grok vision is temporarily unavailable; skipping "
                            "figure analysis for 60 seconds. PDF text extraction continues."
                        )
                        return ""

                    is_rate_limited = (
                        "429" in error_text
                        or "rate_limit" in error_text.casefold()
                        or "resource_exhausted" in error_text.casefold()
                    )
                    if not is_rate_limited or attempt == 4:
                        raise

                    retry_match = re.search(
                        r"try again in\s+([\d.]+)\s*(ms|s)",
                        error_text,
                        re.IGNORECASE,
                    )
                    if retry_match:
                        delay = float(retry_match.group(1))
                        if retry_match.group(2).lower() == "ms":
                            delay /= 1000
                    else:
                        delay = min(30, 2 ** (attempt + 1))

                    delay = max(0.5, min(delay, 60))
                    print(
                        f"Vision request rate-limited for {source_location}; "
                        f"retrying in {delay:.1f}s (attempt {attempt + 2}/5)."
                    )
                    time.sleep(delay)
        description = (response.output_text or "").strip()
        if description:
            try:
                cache_file.parent.mkdir(parents=True, exist_ok=True)
                temporary_file = cache_file.with_name(
                    f"{cache_file.stem}.{os.getpid()}."
                    f"{threading.get_ident()}.tmp"
                )
                temporary_file.write_text(description, encoding="utf-8")
                temporary_file.replace(cache_file)
            except OSError as cache_error:
                print(f"Could not save visual cache: {cache_error}")
        return description
    except Exception as error:
        print(f"Visual extraction failed for {source_location}: {error}")
        return ""
