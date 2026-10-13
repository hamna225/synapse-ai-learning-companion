import re

from youtube_transcript_api import YouTubeTranscriptApi
from langchain_core.documents import Document


def extract_video_id(url):
    patterns = [
        r"v=([^&]+)",
        r"youtu\.be/([^?]+)",
        r"youtube\.com/shorts/([^?]+)"
    ]

    for pattern in patterns:
        match = re.search(pattern, url)

        if match:
            return match.group(1)

    return None


def format_time(seconds):
    seconds = int(seconds)

    minutes = seconds // 60
    seconds = seconds % 60

    return f"{minutes:02d}:{seconds:02d}"


def load_youtube(url):

    video_id = extract_video_id(url)

    if not video_id:
        raise ValueError("Invalid YouTube URL")

    api = YouTubeTranscriptApi()

    # -------------------------------------------------
    # GET AVAILABLE TRANSCRIPTS
    # -------------------------------------------------

    try:
        transcript_list = api.list(video_id)

    except Exception as e:
        raise ValueError(
            f"Could not access YouTube transcripts: {str(e)}"
        )

    available = list(transcript_list)

    if not available:
        raise ValueError(
            "No transcript is available for this YouTube video."
        )

    print("\n" + "=" * 60)
    print("AVAILABLE YOUTUBE TRANSCRIPTS")
    print("=" * 60)

    for transcript in available:

        print(
            "Language:",
            transcript.language_code,
            "|",
            transcript.language,
            "| Generated:",
            transcript.is_generated
        )

    print("=" * 60)

    # -------------------------------------------------
    # CHOOSE TRANSCRIPT
    # -------------------------------------------------

    selected = None

    # Prefer English
    for transcript in available:

        if transcript.language_code == "en":
            selected = transcript
            break

    # If English doesn't exist,
    # use the first available transcript
    if selected is None:
        selected = available[0]

    print(
        "\nSELECTED TRANSCRIPT:",
        selected.language_code,
        selected.language
    )

    # -------------------------------------------------
    # FETCH TRANSCRIPT
    # -------------------------------------------------

    transcript = selected.fetch()

    # -------------------------------------------------
    # CREATE DOCUMENT CHUNKS
    # -------------------------------------------------

    documents = []

    current_text = []
    chunk_start = None
    chunk_end = None

    max_characters = 1200

    for item in transcript:

        text = item.text.strip()

        if not text:
            continue

        start = item.start
        end = item.start + item.duration

        if chunk_start is None:
            chunk_start = start

        current_text.append(text)

        chunk_end = end

        combined_text = " ".join(current_text)

        if len(combined_text) >= max_characters:

            documents.append(
                Document(
                    page_content=combined_text,
                    metadata={
                        "source": url,
                        "source_type": "youtube",
                        "video_id": video_id,
                        "language": selected.language_code,
                        "start_time": chunk_start,
                        "end_time": chunk_end,
                        "timestamp": (
                            f"{format_time(chunk_start)} - "
                            f"{format_time(chunk_end)}"
                        )
                    }
                )
            )

            current_text = []
            chunk_start = None
            chunk_end = None

    # -------------------------------------------------
    # ADD REMAINING TEXT
    # -------------------------------------------------

    if current_text:

        combined_text = " ".join(current_text)

        documents.append(
            Document(
                page_content=combined_text,
                metadata={
                    "source": url,
                    "source_type": "youtube",
                    "video_id": video_id,
                    "language": selected.language_code,
                    "start_time": chunk_start,
                    "end_time": chunk_end,
                    "timestamp": (
                        f"{format_time(chunk_start)} - "
                        f"{format_time(chunk_end)}"
                    )
                }
            )
        )

    print(
        "\nTOTAL YOUTUBE DOCUMENTS:",
        len(documents)
    )

    return documents