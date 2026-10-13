"""Small Groq vision helper for describing figures during material ingestion."""

import base64
from io import BytesIO
import os

from dotenv import load_dotenv
from groq import Groq
from PIL import Image


load_dotenv()
_client = None


def describe_visual(image_bytes, source_location, surrounding_text=""):
    """Return a concise, source-local description, or empty text on failure."""
    global _client

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        print("Visual extraction skipped: GROQ_API_KEY is not configured.")
        return ""

    try:
        image = Image.open(BytesIO(image_bytes)).convert("RGB")
        image.thumbnail((1280, 1280))
        image_buffer = BytesIO()
        image.save(image_buffer, format="JPEG", quality=82, optimize=True)
        encoded_image = base64.b64encode(image_buffer.getvalue()).decode("ascii")

        if _client is None:
            _client = Groq(api_key=api_key, timeout=45)

        response = _client.chat.completions.create(
            model=os.getenv("GROQ_VISION_MODEL", "qwen/qwen3.8-27b"),
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                f"Analyze this figure from {source_location}. "
                                f"Nearby course text: {surrounding_text[:1200]}\n"
                                "Describe only information visibly supported by the image. "
                                "Capture diagram parts and relationships, flow direction, "
                                "chart axes/trends, and legible labels. Do not guess at "
                                "unclear details. Do not infer an icon's intended meaning "
                                "from nearby text; describe the icon literally unless the "
                                "image labels or connects it to a concept. Return a concise "
                                "description under 140 words."
                            ),
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{encoded_image}"
                            },
                        },
                    ],
                }
            ],
            temperature=0,
            max_tokens=220,
        )
        return (response.choices[0].message.content or "").strip()
    except Exception as error:
        print(f"Visual extraction failed for {source_location}: {error}")
        return ""
