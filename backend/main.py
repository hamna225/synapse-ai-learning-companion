from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from langchain_core.documents import Document

from uuid import uuid4

import os
import json
import re
from difflib import SequenceMatcher
try:
    import pythoncom
    import win32com.client
except ImportError:
    pythoncom = None
    win32com = None

from typing import List, Dict, Any, Optional, Union

from ingestion.youtube_loader import load_youtube
from ingestion.pdf_loader import load_pdf
from ingestion.ppt_loader import load_ppt

from rag.chunker import create_chunks
from rag.embeddings import get_embeddings
from rag.vectorstore import create_vectorstore

from agents.tutor_agent import (
    get_tutor,
    get_llm,
)

from assessment.generator import (
    generate_mcq,
    generate_answer_explanation,
)

from assessment.evaluator import evaluate_quiz

from assessment.adaptive_engine import (
    next_difficulty,
    calculate_topic_performance,
    calculate_subtopic_performance,
    select_next_subtopic,
)
from student_analytics.learner_profile import (
    choose_starting_difficulty,
    complete_quiz,
    get_topic_record,
    load_profile,
    record_answer,
)


# =========================================================
# QUIZ SESSION STORAGE
# =========================================================



# =======================
# =========================================================
# QUIZ SESSION STORAGE
# =========================================================

quiz_sessions: Dict[str, Dict[str, Any]] = {}

# Track previously used questions for each material.
# This history resets when FastAPI restarts.
used_quiz_questions: Dict[str, set] = {}


# =========================================================
# NORMALIZE QUESTION TEXT
# =========================================================

def normalize_question_text(question: Any) -> str:
    """Normalize question text to identify duplicate questions."""
    text = str(question or "").casefold().strip()
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"[^\w\s]", "", text)
    return text.strip()


def is_similar_question(question: Any, previous_questions: List[str]) -> bool:
    normalized = normalize_question_text(question)
    if not normalized:
        return False

    return any(
        SequenceMatcher(
            None,
            normalized,
            normalize_question_text(previous),
        ).ratio() >= 0.86
        for previous in previous_questions
        if previous
    )


# =========================================================
# GENERATE A UNIQUE MCQ
# =========================================================

def generate_unique_mcq(
    material_id: str,
    topic: str,
    subtopic: str,
    difficulty: str,
    existing_questions: Optional[List[Dict[str, Any]]] = None,
    max_attempts: int = 8,
) -> Dict[str, Any]:
    """Generate a valid MCQ that has not been used before."""

    history = used_quiz_questions.setdefault(material_id, set())

    existing_texts = {
        normalize_question_text(item.get("question", ""))
        for item in (existing_questions or [])
        if isinstance(item, dict)
    }
    rejected_questions: List[str] = []

    for attempt in range(max_attempts):
        candidate = generate_mcq(
            material_id=material_id,
            topic=topic,
            subtopic=subtopic,
            difficulty=difficulty,
            previous_questions=(
                [item.get("question", "") for item in (existing_questions or []) if isinstance(item, dict)]
                + list(history)
                + rejected_questions
            )[-12:],
        )

        if not isinstance(candidate, dict):
            continue

        question_text = normalize_question_text(
            candidate.get("question", "")
        )

        options = candidate.get("options", {})
        correct_answer = str(
            candidate.get("correct_answer", "")
        ).strip().upper()

        if (
            not question_text
            or not isinstance(options, dict)
            or not all(key in options for key in ("A", "B", "C", "D"))
            or correct_answer not in ("A", "B", "C", "D")
        ):
            continue

        if (
            question_text in history
            or question_text in existing_texts
            or is_similar_question(
                question_text,
                list(existing_texts | history),
            )
        ):
            rejected_questions.append(
                str(candidate.get("question", "")).strip()
            )
            print(
                f"Duplicate or invalid MCQ rejected "
                f"(attempt {attempt + 1}/{max_attempts})."
            )
            continue

        history.add(question_text)
        return candidate

    raise HTTPException(
        status_code=503,
        detail=(
            "Could not generate a new valid question after multiple attempts. "
            "Please try again."
        ),
    )
#==================================
# APP
# =========================================================

app = FastAPI(
    title="AI Adaptive Learning Companion",
    version="1.0.0",
)

@app.get("/")
def health_check():
    return {
        "status": "online",
        "message": "AI Adaptive Learning Companion backend is running"
    }

# =========================================================
# CORS
# =========================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        origin.strip().rstrip("/")
        for origin in os.getenv("FRONTEND_ORIGINS", "").split(",")
        if origin.strip()
    ],
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1):517[0-9]+",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =========================================================
# REQUEST MODELS
# =========================================================

class SessionRequest(BaseModel):
    student_id: str


class AskRequest(BaseModel):
    material_id: Optional[str] = None
    question: str


class TopicsRequest(BaseModel):
    material_id: str


class SubjectiveRequest(BaseModel):
    material_id: str
    material_name: str
    topics: List[str]
    num_questions: int
    difficulty: str


# =========================================================
# QUIZ TOPIC MODEL
# =========================================================

class QuizTopic(BaseModel):
    topic: str
    subtopics: List[str] = Field(default_factory=list)


# =========================================================
# IMPORTANT
#
# This accepts BOTH:
#
# OLD:
# "topics": [
#     "Theory of Automata",
#     "Language Definitions"
# ]
#
# NEW:
# "topics": [
#     {
#         "topic": "Theory of Automata",
#         "subtopics": [
#             "Formal vs Informal Languages",
#             "Finite Automata"
#         ]
#     }
# ]
# =========================================================

QuizTopicInput = Union[str, QuizTopic]


class QuizStartRequest(BaseModel):
    material_id: str
    topics: List[QuizTopicInput]
    num_questions: int = 10
    difficulty: str = "medium"


class QuizAnswerRequest(BaseModel):
    quiz_id: str
    answer: str


# =========================================================
# ROBUST JSON PARSER
# =========================================================

def parse_llm_json(content: str) -> Any:

    if not content:

        raise ValueError(
            "AI returned an empty response."
        )

    text = str(content).strip()

    # -----------------------------------------------------
    # Remove markdown code fences
    # -----------------------------------------------------

    text = re.sub(
        r"^```(?:json)?\s*",
        "",
        text,
        flags=re.IGNORECASE,
    )

    text = re.sub(
        r"\s*```$",
        "",
        text,
    )

    text = text.strip()

    # -----------------------------------------------------
    # Direct JSON
    # -----------------------------------------------------

    try:

        return json.loads(text)

    except json.JSONDecodeError:

        pass

    # -----------------------------------------------------
    # JSON object inside extra text
    # -----------------------------------------------------

    object_start = text.find("{")
    object_end = text.rfind("}")

    if (
        object_start != -1
        and object_end > object_start
    ):

        json_text = text[
            object_start:object_end + 1
        ]

        try:

            return json.loads(
                json_text
            )

        except json.JSONDecodeError:

            pass

    # -----------------------------------------------------
    # JSON array inside extra text
    # -----------------------------------------------------

    array_start = text.find("[")
    array_end = text.rfind("]")

    if (
        array_start != -1
        and array_end > array_start
    ):

        json_text = text[
            array_start:array_end + 1
        ]

        try:

            return json.loads(
                json_text
            )

        except json.JSONDecodeError:

            pass

    # -----------------------------------------------------
    # DEBUG
    # -----------------------------------------------------

    print("\n" + "=" * 80)
    print("RAW AI RESPONSE - JSON PARSING FAILED")
    print("=" * 80)
    print(content)
    print("=" * 80 + "\n")

    raise ValueError(
        "AI returned invalid JSON."
    )


# =========================================================
# CLEAN FLAT TOPICS
# =========================================================

def clean_topics(
    topics: List[str]
) -> List[str]:

    cleaned = []

    seen = set()

    for topic in topics:

        if topic is None:
            continue

        topic = str(
            topic
        ).strip()

        if not topic:
            continue

        normalized = topic.lower()

        if normalized in seen:
            continue

        seen.add(
            normalized
        )

        cleaned.append(
            topic
        )

    return cleaned


# =========================================================
# FILTER OUT SLIDE ARTIFACTS AND GENERIC HEADINGS
# =========================================================

def is_meaningful_topic(topic: str) -> bool:
    """Reject slide numbers and generic outline headings."""
    if not topic:
        return False

    text = re.sub(r"\s+", " ", str(topic)).strip()
    normalized = text.casefold().strip(" .:-")

    # Standalone numbers, slide labels, and section numbering.
    if re.fullmatch(r"(?:slide|page)?\s*\d+(?:\.\d+)*", normalized):
        return False
    if re.fullmatch(r"(?:\d+|[ivxlcdm]+)[.)]?", normalized):
        return False

    generic_headings = {
        "what we'll cover",
        "what we will cover",
        "learning objectives",
        "table of contents",
        "contents",
        "agenda",
        "outline",
        "course outline",
        "course contents",
        "key takeaways",
        "next steps",
        "thank you",
        "introduction",
        "overview",
        "conclusion",
        "summary",
    }

    if normalized in generic_headings:
        return False

    return len(normalized) >= 2


def filter_meaningful_topics(
    topics: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Clean topic names and subtopics without changing their hierarchy."""
    result = []
    seen_topics = set()

    for item in topics or []:
        if not isinstance(item, dict):
            continue

        topic = str(item.get("topic", "")).strip()
        if not is_meaningful_topic(topic):
            continue

        topic_key = topic.casefold()
        if topic_key in seen_topics:
            continue
        seen_topics.add(topic_key)

        raw_subtopics = item.get("subtopics", [])
        if not isinstance(raw_subtopics, list):
            raw_subtopics = []

        cleaned_subtopics = []
        seen_subtopics = set()

        for subtopic in raw_subtopics:
            subtopic = str(subtopic or "").strip()
            if not is_meaningful_topic(subtopic):
                continue

            subtopic_key = subtopic.casefold()
            if subtopic_key == topic_key or subtopic_key in seen_subtopics:
                continue

            seen_subtopics.add(subtopic_key)
            cleaned_subtopics.append(subtopic)

        result.append({
            "topic": topic,
            "subtopics": cleaned_subtopics or [topic],
        })

    return result


# =========================================================
# CLEAN HIERARCHICAL TOPICS
#
# Accepts both string and QuizTopic.
# =========================================================

def clean_hierarchical_topics(
    topics: List[QuizTopicInput]
) -> List[Dict[str, Any]]:

    cleaned_topics = []

    seen_main_topics = set()

    for topic_item in topics:

        # =================================================
        # OLD FLAT FORMAT
        # =================================================

        if isinstance(
            topic_item,
            str
        ):

            main_topic = (
                topic_item.strip()
            )

            raw_subtopics = []

        # =================================================
        # NEW HIERARCHICAL FORMAT
        # =================================================

        elif isinstance(
            topic_item,
            QuizTopic
        ):

            main_topic = (
                topic_item.topic.strip()
            )

            raw_subtopics = (
                topic_item.subtopics
            )

        else:

            continue

        # =================================================
        # VALIDATE MAIN TOPIC
        # =================================================

        if not main_topic:
            continue

        normalized_main = (
            main_topic.lower()
        )

        # -------------------------------------------------
        # Duplicate main topic
        # -------------------------------------------------

        if normalized_main in seen_main_topics:

            continue

        seen_main_topics.add(
            normalized_main
        )

        # =================================================
        # CLEAN SUBTOPICS
        # =================================================

        cleaned_subtopics = []

        seen_subtopics = set()

        for subtopic in raw_subtopics:

            if subtopic is None:
                continue

            subtopic = str(
                subtopic
            ).strip()

            if not subtopic:
                continue

            normalized_subtopic = (
                subtopic.lower()
            )

            if normalized_subtopic in seen_subtopics:
                continue

            seen_subtopics.add(
                normalized_subtopic
            )

            cleaned_subtopics.append(
                subtopic
            )

        # =================================================
        # FALLBACK
        #
        # If original frontend sends only:
        #
        # "Theory of Automata"
        #
        # then the main topic itself becomes its
        # temporary subtopic.
        # =================================================

        if not cleaned_subtopics:

            cleaned_subtopics = [
                main_topic
            ]

        cleaned_topics.append(
            {
                "topic": main_topic,
                "subtopics": cleaned_subtopics,
            }
        )

    return cleaned_topics


# =========================================================
# GET ALL SUBTOPICS
# =========================================================

def get_all_subtopics(
    topic_groups: List[Dict[str, Any]]
) -> List[Dict[str, str]]:

    result = []

    for group in topic_groups:

        main_topic = group.get(
            "topic",
            ""
        )

        subtopics = group.get(
            "subtopics",
            []
        )

        for subtopic in subtopics:

            result.append(
                {
                    "topic": main_topic,
                    "subtopic": subtopic,
                }
            )

    return result


# =========================================================
# FIND TOPIC GROUP
# =========================================================

def find_topic_group(
    topic_groups: List[Dict[str, Any]],
    topic_name: str,
) -> Optional[Dict[str, Any]]:

    normalized = (
        str(topic_name)
        .strip()
        .lower()
    )

    for group in topic_groups:

        if (
            str(
                group.get(
                    "topic",
                    ""
                )
            )
            .strip()
            .lower()
            == normalized
        ):

            return group

    return None


# =========================================================
# FIND NEXT MAIN TOPIC
# =========================================================

def select_next_main_topic(
    topic_groups: List[Dict[str, Any]],
    current_topic: str,
    topic_scores: Dict[str, Any],
    current_subtopic: str,
    subtopic_scores: Dict[str, Any],
) -> Optional[str]:

    if not topic_groups:
        return None

    # =====================================================
    # FIRST PRIORITY:
    # Find a main topic that has never been tested.
    # =====================================================

    for group in topic_groups:

        topic = group.get(
            "topic",
            ""
        ).strip()

        if not topic:
            continue

        score = topic_scores.get(
            topic
        )

        if not score:
            return topic

    # =====================================================
    # SECOND PRIORITY:
    # Stay with current topic if it still has an
    # untested subtopic.
    # =====================================================

    current_group = find_topic_group(
        topic_groups,
        current_topic,
    )

    if current_group:

        current_subtopics = (
            current_group.get(
                "subtopics",
                []
            )
        )

        for subtopic in current_subtopics:

            if subtopic not in subtopic_scores:

                return current_topic

    # =====================================================
    # THIRD PRIORITY:
    # Move to weakest main topic.
    # =====================================================

    weakest_topic = None
    weakest_percentage = 101

    for group in topic_groups:

        topic = group.get(
            "topic",
            ""
        ).strip()

        if not topic:
            continue

        score = topic_scores.get(
            topic,
            {}
        )

        percentage = score.get(
            "percentage",
            0
        )

        if percentage < weakest_percentage:

            weakest_percentage = percentage
            weakest_topic = topic

    return weakest_topic


# =========================================================
# SELECT NEXT SUBTOPIC FOR A MAIN TOPIC
# =========================================================

def select_subtopic_for_topic(
    topic_group: Dict[str, Any],
    subtopic_scores: Dict[str, Any],
    current_subtopic: Optional[str] = None,
) -> Optional[str]:

    subtopics = topic_group.get(
        "subtopics",
        []
    )

    # If this topic has no subtopics,
    # use the main topic name
    if not subtopics:
        return topic_group.get("topic")

    # Clean subtopics
    cleaned_subtopics = []

    seen = set()

    for subtopic in subtopics:

        if subtopic is None:
            continue

        subtopic = str(subtopic).strip()

        if not subtopic:
            continue

        normalized = subtopic.lower()

        if normalized in seen:
            continue

        seen.add(normalized)

        cleaned_subtopics.append(subtopic)

    if not cleaned_subtopics:
        return topic_group.get("topic")

    # =====================================================
    # 1. FIRST: FIND AN UNATTEMPTED SUBTOPIC
    # =====================================================

    for subtopic in cleaned_subtopics:

        if subtopic not in subtopic_scores:

            # Don't immediately repeat the current subtopic
            if (
                current_subtopic is None
                or subtopic.lower()
                != str(current_subtopic).lower().strip()
            ):
                return subtopic

    # =====================================================
    # 2. IF EVERYTHING WAS ATTEMPTED
    #    CHOOSE THE WEAKEST DIFFERENT SUBTOPIC
    # =====================================================

    other_subtopics = []

    for subtopic in cleaned_subtopics:

        if (
            current_subtopic is None
            or subtopic.lower()
            != str(current_subtopic).lower().strip()
        ):
            other_subtopics.append(subtopic)

    if other_subtopics:

        return min(
            other_subtopics,
            key=lambda subtopic:
                subtopic_scores.get(
                    subtopic,
                    {}
                ).get(
                    "percentage",
                    0
                )
        )

    # =====================================================
    # 3. ONLY ONE SUBTOPIC EXISTS
    # =====================================================

    return cleaned_subtopics[0]
    # =====================================================
    # First test every unseen subtopic.
    # =====================================================

    for subtopic in subtopics:

        if subtopic not in subtopic_scores:

            return subtopic

    # =====================================================
    # Then select weakest subtopic.
    # =====================================================

    return select_next_subtopic(
        subtopics,
        subtopic_scores
    )


# =========================================================
# PPT → PPTX CONVERSION
# =========================================================

def convert_ppt_to_pptx(
    ppt_path: str,
    output_path: str,
) -> str:

    ppt_path = os.path.abspath(
        ppt_path
    )

    output_path = os.path.abspath(
        output_path
    )

    output_dir = os.path.dirname(
        output_path
    )

    os.makedirs(
        output_dir,
        exist_ok=True,
    )

    powerpoint = None
    presentation = None

    try:

        print("=" * 70)

        print(
            "Starting Microsoft PowerPoint conversion"
        )

        print(
            f"Input : {ppt_path}"
        )

        print(
            f"Output: {output_path}"
        )

        print("=" * 70)

        powerpoint = (
            win32com.client.DispatchEx(
                "PowerPoint.Application"
            )
        )

        powerpoint.Visible = True

        presentation = (
            powerpoint.Presentations.Open(
                ppt_path,
                ReadOnly=True,
                WithWindow=False,
            )
        )

        print(
            "✓ PPT file opened successfully"
        )

        presentation.SaveAs(
            output_path,
            24,
        )

        print(
            "✓ PPT converted to PPTX"
        )

        if not os.path.exists(
            output_path
        ):

            raise RuntimeError(
                "PowerPoint conversion completed, "
                "but the converted PPTX file was not created."
            )

        if os.path.getsize(
            output_path
        ) == 0:

            raise RuntimeError(
                "PowerPoint created an empty PPTX file."
            )

        print(
            f"✓ Converted file verified: {output_path}"
        )

        return output_path

    except Exception as e:

        print(
            "PowerPoint conversion error:",
            str(e),
        )

        raise RuntimeError(
            "Microsoft PowerPoint could not convert "
            f"the .ppt file. Error: {str(e)}"
        )

    finally:

        if presentation is not None:

            try:

                presentation.Close()

            except Exception as close_error:

                print(
                    "Warning: Could not close presentation:",
                    close_error,
                )

        if powerpoint is not None:

            try:

                powerpoint.Quit()

            except Exception as quit_error:

                print(
                    "Warning: Could not quit PowerPoint:",
                    quit_error,
                )


# =========================================================
# CREATE LEARNING SESSION
# =========================================================

@app.post("/sessions")
def create_session(
    request: SessionRequest
):

    session_id = (
        f"session_{uuid4().hex[:12]}"
    )

    return {

        "message":
            "Learning session created successfully",

        "student_id":
            request.student_id,

        "session_id":
            session_id,
    }


# =========================================================
# UPLOAD PDF / PPT / PPTX
# =========================================================

@app.post(
    "/sessions/{session_id}/materials"
)
async def upload_material(
    session_id: str,
    file: UploadFile = File(...),
):

    allowed_extensions = {
        ".pdf",
        ".ppt",
        ".pptx",
    }

    if not file.filename:

        raise HTTPException(
            status_code=400,
            detail="File name is missing.",
        )

    original_filename = file.filename

    file_extension = os.path.splitext(
        original_filename
    )[1].lower()

    if file_extension not in allowed_extensions:

        raise HTTPException(
            status_code=400,
            detail=(
                "Only PDF, PPT, and PPTX files are supported."
            ),
        )

    upload_dir = (
        "uploaded_materials"
    )

    os.makedirs(
        upload_dir,
        exist_ok=True,
    )

    material_id = (
        f"material_{uuid4().hex[:12]}"
    )

    file_path = os.path.join(
        upload_dir,
        f"{material_id}_{original_filename}",
    )

    try:

        file_content = await file.read()

        with open(
            file_path,
            "wb",
        ) as buffer:

            buffer.write(
                file_content
            )

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=(
                f"Failed to save uploaded file: {str(e)}"
            ),
        )

    processing_path = file_path

    converted_from_ppt = False

    if file_extension == ".pdf":

        try:

            documents = load_pdf(
                processing_path
            )

        except Exception as e:

            raise HTTPException(
                status_code=400,
                detail=(
                    f"Failed to read PDF file: {str(e)}"
                ),
            )

    elif file_extension == ".pptx":

        try:

            documents = load_ppt(
                processing_path
            )

        except Exception as e:

            raise HTTPException(
                status_code=400,
                detail=(
                    f"Failed to read PPTX file: {str(e)}"
                ),
            )

    elif file_extension == ".ppt":

        try:

            converted_dir = os.path.join(
                upload_dir,
                "converted",
            )

            os.makedirs(
                converted_dir,
                exist_ok=True,
            )

            converted_path = os.path.join(
                converted_dir,
                f"{material_id}.pptx",
            )

            processing_path = (
                convert_ppt_to_pptx(
                    file_path,
                    converted_path,
                )
            )

            converted_from_ppt = True

            documents = load_ppt(
                processing_path
            )

        except Exception as e:

            print(
                "PPT conversion/reading error:",
                str(e),
            )

            raise HTTPException(
                status_code=400,
                detail=(
                    "This .ppt file could not be processed. "
                    "Make sure Microsoft PowerPoint is installed "
                    "and the file is not corrupted. "
                    f"Error: {str(e)}"
                ),
            )

    else:

        documents = []

    if not documents:

        raise HTTPException(
            status_code=400,
            detail=(
                "No readable content was found in the file."
            ),
        )

    for document in documents:

        document.metadata[
            "session_id"
        ] = session_id

        document.metadata[
            "material_id"
        ] = material_id

        document.metadata[
            "material_name"
        ] = original_filename

        document.metadata[
            "file_type"
        ] = file_extension

        document.metadata[
            "converted_from_ppt"
        ] = converted_from_ppt

    try:

        chunks = create_chunks(
            documents
        )

    except Exception as e:

        raise HTTPException(
            status_code=400,
            detail=(
                f"Failed to create chunks: {str(e)}"
            ),
        )

    if not chunks:

        raise HTTPException(
            status_code=400,
            detail=(
                "No usable chunks were created from the material."
            ),
        )

    try:

        embeddings = get_embeddings()

        collection_name = material_id

        create_vectorstore(
            chunks,
            embeddings,
            collection_name=collection_name,
        )

    except Exception as e:

        print(
            "Vector store creation error:",
            str(e),
        )

        raise HTTPException(
            status_code=500,
            detail=(
                f"Failed to create vector store: {str(e)}"
            ),
        )

    return {

        "message":
            "Material uploaded successfully",

        "session_id":
            session_id,

        "material_id":
            material_id,

        "filename":
            original_filename,

        "file_type":
            file_extension,

        "converted_from_ppt":
            converted_from_ppt,

        "processed_file_type":
            (
                ".pptx"
                if converted_from_ppt
                else file_extension
            ),

        "documents":
            len(documents),

        "chunks":
            len(chunks),

        "collection":
            collection_name,
    }


# =========================================================
# UPLOAD YOUTUBE
# =========================================================

@app.post(
    "/sessions/{session_id}/youtube"
)
async def upload_youtube(
    session_id: str,
    youtube_url: str = Form(...),
):

    try:

        print("\n" + "=" * 60)

        print(
            "YOUTUBE URL:",
            youtube_url
        )

        print("=" * 60)

        documents = load_youtube(
            youtube_url
        )

        if not documents:

            raise HTTPException(
                status_code=400,
                detail=(
                    "No transcript found for this YouTube video."
                ),
            )

        material_id = (
            f"youtube_{uuid4().hex[:12]}"
        )

        for document in documents:

            document.metadata[
                "session_id"
            ] = session_id

            document.metadata[
                "material_id"
            ] = material_id

            document.metadata[
                "source_type"
            ] = "youtube"

            document.metadata[
                "youtube_url"
            ] = youtube_url

        chunks = documents

        print("\n" + "=" * 60)

        print(
            "YOUTUBE CHUNKS:",
            len(chunks)
        )

        for i, chunk in enumerate(
            chunks[:3],
            1,
        ):

            print(
                f"\nVIDEO CHUNK {i}:"
            )

            print(
                chunk.page_content[:500]
            )

            print(
                "METADATA:"
            )

            print(
                chunk.metadata
            )

            print(
                "-" * 60
            )

        print("=" * 60)

        embeddings = get_embeddings()

        collection_name = material_id

        create_vectorstore(
            chunks,
            embeddings,
            collection_name=collection_name,
        )

        return {

            "message":
                "YouTube video added successfully",

            "session_id":
                session_id,

            "material_id":
                material_id,

            "youtube_url":
                youtube_url,

            "source_type":
                "youtube",

            "documents":
                len(documents),

            "chunks":
                len(chunks),

            "collection":
                collection_name,
        }

    except HTTPException:

        raise

    except Exception as e:

        print("\n" + "=" * 60)

        print(
            "YOUTUBE UPLOAD ERROR"
        )

        print(
            str(e)
        )

        print("=" * 60)

        raise HTTPException(
            status_code=400,
            detail=str(e),
        )


# =========================================================
# ASK QUESTION
# =========================================================

@app.get("/materials/{material_id}/source")
def get_material_source(material_id: str):
    """Serve an uploaded source file for tutor citations."""
    if not re.fullmatch(r"material_[a-fA-F0-9]+", material_id):
        raise HTTPException(status_code=400, detail="Invalid material ID.")

    upload_dir = os.path.abspath("uploaded_materials")
    try:
        filename = next(
            name for name in os.listdir(upload_dir)
            if name.startswith(f"{material_id}_")
        )
    except (FileNotFoundError, StopIteration):
        raise HTTPException(status_code=404, detail="Source file not found.")

    source_path = os.path.join(upload_dir, filename)
    extension = os.path.splitext(filename)[1].lower()

    if extension in {".ppt", ".pptx"}:
        preview_dir = os.path.join(upload_dir, "converted")
        os.makedirs(preview_dir, exist_ok=True)
        preview_path = os.path.join(preview_dir, f"{material_id}_preview.pdf")

        if not os.path.exists(preview_path):
            if pythoncom is None or win32com is None:
                raise HTTPException(
                    status_code=501,
                    detail=(
                        "PowerPoint preview conversion requires Microsoft "
                        "PowerPoint on Windows."
                    ),
                )

            presentation_path = source_path
            if extension == ".ppt":
                presentation_path = os.path.join(preview_dir, f"{material_id}.pptx")
                if not os.path.exists(presentation_path):
                    convert_ppt_to_pptx(source_path, presentation_path)

            powerpoint = None
            presentation = None
            com_initialized = False
            try:
                pythoncom.CoInitialize()
                com_initialized = True
                powerpoint = win32com.client.DispatchEx("PowerPoint.Application")
                presentation = powerpoint.Presentations.Open(
                    os.path.abspath(presentation_path),
                    ReadOnly=True,
                    WithWindow=False,
                )
                presentation.SaveAs(os.path.abspath(preview_path), 32)
            except Exception as e:
                raise HTTPException(
                    status_code=500,
                    detail=f"Could not create a browser preview for this presentation: {e}",
                )
            finally:
                if presentation is not None:
                    presentation.Close()
                if powerpoint is not None:
                    powerpoint.Quit()
                if com_initialized:
                    pythoncom.CoUninitialize()

        return FileResponse(
            preview_path,
            media_type="application/pdf",
            filename=f"{material_id}.pdf",
            content_disposition_type="inline",
        )

    return FileResponse(
        source_path,
        media_type="application/pdf",
        filename=filename,
        content_disposition_type="inline",
    )

@app.post("/ask")
def ask_question(
    request: AskRequest,
):

    try:

        # =====================================================
        # GENERAL AI MODE
        # =====================================================

        if not request.material_id:

            llm = get_llm()

            prompt = f"""
You are a professional AI Tutor helping a university student.

The student has NOT selected any learning material.

Answer the student's question using your general knowledge.

Make the answer look like a well-written university study note.

IMPORTANT RULES:

- Never use Markdown tables.
- Never use the | character for formatting.
- Never use horizontal lines.
- Keep headings short and meaningful.
- Keep paragraphs short and easy to read.
- Use numbered lists for steps.
- Use bullet points for key points.
- Use bold text only for important terms.
- Do not repeat the question.
- Do not add source citations.
- Do not add a Sources section.

STUDENT QUESTION:

{request.question}

Now answer the student.
"""

            response = llm.invoke(
                prompt
            )

            return {

                "answer":
                    response.content,

                "mode":
                    "general",
            }

        # =====================================================
        # MATERIAL / RAG MODE
        # =====================================================

        print("\n" + "=" * 80)

        print(
            "ASK MATERIAL ID:",
            request.material_id
        )

        print(
            "ASK QUESTION:",
            request.question
        )

        print("=" * 80)

        llm, retriever = get_tutor(
            request.material_id
        )

        requested_slide = re.search(
            r"\bslide\s*#?\s*(\d+)\b",
            request.question,
            re.IGNORECASE,
        )
        requested_page = re.search(
            r"\bpage\s*#?\s*(\d+)\b",
            request.question,
            re.IGNORECASE,
        )
        if requested_slide:
            docs = retriever.vectorstore.similarity_search(
                request.question,
                k=5,
                filter={"slide": int(requested_slide.group(1))},
            )
        elif requested_page:
            docs = retriever.vectorstore.similarity_search(
                request.question,
                k=5,
                filter={"page": int(requested_page.group(1))},
            )
        else:
            docs = retriever.invoke(request.question)

        print("\n" + "=" * 80)

        print(
            "RETRIEVED DOCUMENTS:",
            len(docs)
        )

        for i, doc in enumerate(
            docs[:5],
            1,
        ):

            print(
                f"\nDOCUMENT {i}"
            )

            print(
                "TEXT:"
            )

            print(
                doc.page_content[:1000]
            )

            print(
                "METADATA:"
            )

            print(
                doc.metadata
            )

            print(
                "-" * 60
            )

        print("=" * 80 + "\n")

        # Keep the full top-five retrieval set. Relevant course slides can rank
        # fourth or fifth (for example, slide 6 for a question about learning types).
        docs = docs[:5]

        context_parts = []
        for index, doc in enumerate(docs, 1):
            if not hasattr(doc, "page_content"):
                continue
            metadata = doc.metadata or {}
            if metadata.get("slide") is not None:
                location = f"Slide {metadata['slide']}"
            elif metadata.get("page") is not None:
                location = f"Page {metadata['page']}"
            else:
                location = metadata.get("timestamp", "Source")
            context_parts.append(
                f"[{index}] ({location}) {doc.page_content}"
            )
        context = "\n\n".join(context_parts)

        prompt = f"""
You are a professional AI Tutor helping a university student
understand their uploaded learning material.

Answer the student's question using the provided material.

IMPORTANT RULES:

1. Give a direct and meaningful answer.

2. Explain the concept clearly using simple
   university-level language.

3. First answer using information supported by the provided material.

4. If the material does not explain the answer fully, still answer the
   question using reliable general knowledge. Begin that portion with
   **General explanation (outside the uploaded material):** and do not
   present it as content from the student's material.
   If the requested detail, dataset, algorithm, or task is not present in
   the supplied passages, explicitly state that the uploaded material does
   not cover that specific request before offering any general explanation.
   Do not imply that the material recommends or explains something unless
   the supplied passages say so.
   Exception: when the student names a specific slide or page and the
   supplied passages do not contain that location, say you cannot verify
   its contents from the material. Do not guess or give a generic answer.

5. Do NOT mention:
   - transcript
   - retrieved documents
   - chunks
   - RAG
   - internal system details

6. Clearly distinguish source-supported statements from general knowledge.
   Never attach a course citation to a claim unless the supplied passage
   supports it. If a topic question asks for categories or types, define
   each major category briefly.
   Treat figure descriptions as visual observations, not proof of what an
   unlabeled icon is intended to mean. State an icon's conceptual meaning
   only when the material explicitly connects it to that concept; otherwise
   describe it literally or label the interpretation as general explanation.
   Do not invent symbolic meanings or metaphors for icons (for example,
   claiming a shape evokes a database) unless the material says so.

7. Do not repeat the student's question.

8. Keep the answer focused.

9. Use short paragraphs.

10. Use bullet points or numbered lists when useful.

11. Never use Markdown tables.

12. Cite source-supported statements inline as [1], [2], and so on.
13. Use only citation numbers that correspond to the supplied material passages.
14. Do not make up citations. General knowledge does not need a course citation.
15. A citation number such as [1] identifies a passage, not its slide or page.
    When asked for a slide or page number, use the explicit source location
    shown beside the passage and report that number accurately. Include the
    passage citation too, for example: "Slide 19 [1]" when [1] is labeled
    "Slide 19" in the supplied context.

MATERIAL:

{context}

STUDENT QUESTION:

{request.question}

Now provide a clear answer.
"""

        response = llm.invoke(
            prompt
        )
        answer = str(response.content)

        # For explicit slide/page lookup questions, ensure the returned source
        # link can be tied to the stated location when the model omits [n].
        if re.search(r"\bwhich\s+(?:slide|page)\b", request.question, re.IGNORECASE):
            mentioned_location = re.search(
                r"\b(slide|page)\s*(\d+)\b", answer, re.IGNORECASE
            )
            if mentioned_location:
                location_type = mentioned_location.group(1).casefold()
                location_number = int(mentioned_location.group(2))
                for citation_number, doc in enumerate(docs, 1):
                    metadata = doc.metadata or {}
                    metadata_number = metadata.get(location_type)
                    if metadata_number is None or int(metadata_number) != location_number:
                        continue
                    cited_numbers = {
                        int(value)
                        for value in re.findall(
                            r"(?:\[|【)(\d+)(?:\]|】)", answer
                        )
                    }
                    if citation_number not in cited_numbers:
                        insert_at = mentioned_location.end()
                        answer = (
                            answer[:insert_at]
                            + f" [{citation_number}]"
                            + answer[insert_at:]
                        )
                    break

        sources = []
        for citation_number, doc in enumerate(docs, 1):
            metadata = doc.metadata or {}
            source_type = metadata.get("source_type", "")
            source_url = metadata.get("source", "")
            if source_type == "youtube":
                start_time = int(float(metadata.get("start_time", 0)))
                citation_url = f"{source_url}&t={start_time}s" if "?" in source_url else f"{source_url}?t={start_time}s"
                label = f"Video · {metadata.get('timestamp', 'open source')}"
            elif source_type == "pdf" and metadata.get("page"):
                page = int(metadata["page"])
                citation_url = f"/materials/{request.material_id}/source#page={page}"
                label = f"PDF · Page {page}"
            elif source_type == "ppt" and metadata.get("slide"):
                slide = int(metadata["slide"])
                citation_url = f"/materials/{request.material_id}/source#page={slide}"
                label = f"Slides · Slide {slide}"
            else:
                continue

            sources.append({
                "number": citation_number,
                "label": label,
                "url": citation_url,
            })

        return {

            "answer": answer,

            "mode":
                "material",

            "material_id":
                request.material_id,

            "sources": sources,
        }

    except Exception as e:

        print(
            "\nASK QUESTION ERROR:",
            repr(e)
        )

        raise HTTPException(
            status_code=500,
            detail=str(e),
        )


# =========================================================
# GET TOPICS
# =========================================================

@app.post("/topics")
def get_topics(
    request: TopicsRequest,
):

    try:

        llm, retriever = get_tutor(
            request.material_id
        )

        search_queries = [

            "all topics covered in this lecture",

            "main topics and chapter headings",

            "main concepts discussed",

            "important concepts and definitions",

            "key terms and terminology",

            "major subjects discussed",

            "theory definitions examples",

            "introduction conclusion summary",
        ]

        all_docs = []

        if request.material_id.startswith("youtube_"):
            # Topic discovery needs the transcript in sequence, not a handful
            # of semantically similar but potentially scattered chunks.
            stored = retriever.vectorstore.get(
                include=["documents", "metadatas"]
            )
            segments = zip(
                stored.get("documents") or [],
                stored.get("metadatas") or [],
            )
            for text, metadata in sorted(
                segments,
                key=lambda segment: float(segment[1].get("start_time", 0)),
            ):
                timestamp = metadata.get("timestamp", "")
                all_docs.append(Document(
                    page_content=f"[{timestamp}] {text}" if timestamp else text,
                    metadata=metadata,
                ))
        else:
            for query in search_queries:
                try:
                    docs = retriever.invoke(query)
                    if docs:
                        all_docs.extend(docs)
                except Exception as search_error:
                    print(f"Search failed for '{query}':", search_error)

        unique_text = []

        seen = set()

        for doc in all_docs:

            if not hasattr(
                doc,
                "page_content",
            ):

                continue

            text = (
                doc.page_content
                .strip()
            )

            if not text:
                continue

            key = text[:500]

            if key in seen:
                continue

            seen.add(
                key
            )

            unique_text.append(
                text
            )

        if len(unique_text) < 5:

            fallback_queries = [

                "lecture",
                "course",
                "material",
                "concept",
                "definition",
            ]

            for query in fallback_queries:

                try:

                    docs = retriever.invoke(
                        query
                    )

                    if docs:

                        all_docs.extend(
                            docs
                        )

                except Exception as fallback_error:

                    print(
                        "Fallback search error:",
                        fallback_error
                    )

        unique_text = []

        seen = set()

        for doc in all_docs:

            if not hasattr(
                doc,
                "page_content",
            ):

                continue

            text = (
                doc.page_content
                .strip()
            )

            if not text:
                continue

            key = text[:500]

            if key in seen:
                continue

            seen.add(
                key
            )

            unique_text.append(
                text
            )

        context_parts = []

        total_length = 0

        is_youtube = request.material_id.startswith("youtube_")
        if is_youtube and len(unique_text) > 10:
            # Sample the whole video instead of sending an oversized transcript
            # or taking only its opening minutes.
            sample_indexes = {
                round(index * (len(unique_text) - 1) / 9)
                for index in range(10)
            }
            unique_text = [
                text for index, text in enumerate(unique_text)
                if index in sample_indexes
            ]

        MAX_CONTEXT = 12000 if is_youtube else 30000

        for text in unique_text:

            if total_length >= MAX_CONTEXT:

                break

            remaining = (
                MAX_CONTEXT
                - total_length
            )

            piece = text[
                :remaining
            ]

            context_parts.append(
                piece
            )

            total_length += len(
                piece
            )

        context = "\n\n".join(
            context_parts
        )

        if not context.strip():

            raise ValueError(
                "No readable content was retrieved "
                "from this material."
            )

        prompt = f"""
You are an expert instructional designer creating a useful
Learning Map from a student's uploaded course material.

Identify the real concepts that students should understand
and practice, then group related concepts under meaningful
main topics.

IMPORTANT RULES:
1. Prioritize concepts, principles, methods, algorithms, and skills actually explained.
2. Group related ideas under meaningful parent topics.
3. Main topics should be broad, coherent subjects, not every slide heading or bullet.
4. Put definitions, examples, types, steps, and applications under the appropriate parent as subtopics.
5. Ignore slide/page/section numbers and isolated numbering.
6. Do not use generic headings such as "What We'll Cover", "Introduction",
   "Overview", "Table of Contents", "Learning Objectives", "Key Takeaways",
   "Next Steps", or "Thank You" as standalone topics. A descriptive heading
   such as "Introduction to Machine Learning" is valid if it teaches a concept.
7. Do not make every bullet point a separate main topic.
8. Merge repeated or closely related concepts.
   For video transcripts, use the timestamped excerpts sampled across the video
   and combine related ideas into coherent course topics.
9. Do not invent information that is not supported by the material.
10. Return 1 to 10 meaningful main topics where the material supports them.
11. Keep topic names concise and exam-friendly.
12. Return valid JSON only, with no Markdown or commentary.

Return this structure:
{{
  "topics": [
    {{
      "topic": "Data, Features and Labels",
      "subtopics": [
        "Features as model inputs",
        "Labels as prediction targets",
        "Numerical and categorical data",
        "Unstructured data"
      ]
    }}
  ]
}}

LEARNING MATERIAL:
{context[:50000]}
"""

        response = llm.invoke(
            prompt
        )

        print(
            "\nRAW TOPIC RESPONSE:\n",
            response.content
        )

        parsed = parse_llm_json(
            response.content
        )

        if isinstance(
            parsed,
            dict
        ):

            topics = parsed.get(
                "topics",
                []
            )

        else:

            topics = parsed

        if not isinstance(
            topics,
            list
        ):

            raise ValueError(
                "LLM did not return a valid topic list."
            )

        cleaned_topics = []

        seen_main_topics = set()

        for item in topics:

            if not isinstance(
                item,
                dict
            ):

                continue

            main_topic = str(
                item.get(
                    "topic",
                    ""
                )
            ).strip()

            if not main_topic:
                continue

            normalized_main = (
                main_topic.lower()
            )

            if normalized_main in seen_main_topics:
                continue

            seen_main_topics.add(
                normalized_main
            )

            raw_subtopics = item.get(
                "subtopics",
                []
            )

            if not isinstance(
                raw_subtopics,
                list
            ):

                raw_subtopics = []

            cleaned_subtopics = []

            seen_subtopics = set()

            for subtopic in raw_subtopics:

                subtopic = str(
                    subtopic
                ).strip()

                if not subtopic:
                    continue

                normalized_subtopic = (
                    subtopic.lower()
                )

                if normalized_subtopic in seen_subtopics:
                    continue

                seen_subtopics.add(
                    normalized_subtopic
                )

                cleaned_subtopics.append(
                    subtopic
                )

            cleaned_topics.append(
                {
                    "topic":
                        main_topic,

                    "subtopics":
                        cleaned_subtopics,
                }
            )

        cleaned_topics = filter_meaningful_topics(
            cleaned_topics
        )

        if not cleaned_topics:

            raise ValueError(
                "No meaningful learning topics were found in the material. "
                "Try uploading a text-based PDF or clearer lecture slides."
            )

        print(
            f"\n✓ Extracted {len(cleaned_topics)} meaningful main topics"
        )

        for index, item in enumerate(
            cleaned_topics[:10],
            start=1,
        ):

            print(
                f"{index}. {item['topic']}"
            )

            for subtopic in item[
                "subtopics"
            ]:

                print(
                    f"   - {subtopic}"
                )

        return {
            "topics":
                cleaned_topics[:10]
        }


    except Exception as e:
        print(
            "\nTOPIC EXTRACTION ERROR:",
            repr(e)
        )

        raise HTTPException(
            status_code=500,
            detail=f"Topic extraction failed: {str(e)}"
        )
# =========================================================
# GENERATE SUBJECTIVE QUESTIONS
# =========================================================

@app.post(
    "/generate-subjective"
)
async def generate_subjective(
    request: SubjectiveRequest,
):

    try:

        topics = clean_topics(
            request.topics
        )

        if not topics:

            raise HTTPException(
                status_code=400,
                detail=(
                    "No topics found for this material."
                ),
            )

        if request.num_questions <= 0:

            raise HTTPException(
                status_code=400,
                detail=(
                    "Number of questions must be greater than zero."
                ),
            )

        allowed_difficulties = {
            "easy",
            "medium",
            "hard",
        }

        difficulty = (
            request.difficulty
            .strip()
            .lower()
        )

        if difficulty not in allowed_difficulties:

            raise HTTPException(
                status_code=400,
                detail=(
                    "Difficulty must be Easy, Medium, or Hard."
                ),
            )

        llm, retriever = get_tutor(
            request.material_id
        )

        question_plan = []

        for index in range(
            request.num_questions
        ):

            topic = topics[
                index % len(topics)
            ]

            question_plan.append(
                topic
            )

        topic_context_map = {}

        for topic in topics:

            try:

                docs = retriever.invoke(
                    topic
                )

                docs = docs[:5]

                context_parts = []

                for doc in docs:

                    if not hasattr(
                        doc,
                        "page_content",
                    ):

                        continue

                    content = (
                        doc.page_content
                        .strip()
                    )

                    if content:

                        context_parts.append(
                            content
                        )

                topic_context_map[
                    topic
                ] = (
                    "\n\n".join(
                        context_parts
                    )[:7000]
                )

            except Exception as e:

                print(
                    f"Topic retrieval failed for '{topic}':",
                    str(e),
                )

                topic_context_map[
                    topic
                ] = ""

        BATCH_SIZE = 5

        all_questions = []

        for start in range(
            0,
            len(question_plan),
            BATCH_SIZE,
        ):

            batch_topics = question_plan[
                start:start + BATCH_SIZE
            ]

            number_for_batch = len(
                batch_topics
            )

            unique_batch_topics = list(
                dict.fromkeys(
                    batch_topics
                )
            )

            batch_context_parts = []

            for topic in unique_batch_topics:

                context = (
                    topic_context_map.get(
                        topic,
                        "",
                    )
                )

                batch_context_parts.append(
                    f"""
TOPIC: {topic}

STUDY MATERIAL:
{context}
"""
                )

            batch_context = "\n".join(
                batch_context_parts
            )

            prompt = f"""
You are an experienced university teacher,
exam paper setter, and academic tutor.

Generate short subjective questions for a BSCS
university examination.

MATERIAL:
{request.material_name}

DIFFICULTY:
{difficulty}

NUMBER OF QUESTIONS:
{number_for_batch}

ASSIGNED TOPICS:
{json.dumps(batch_topics)}

STUDY MATERIAL:
{batch_context}

Generate EXACTLY {number_for_batch} questions.

Every question MUST belong to exactly one
assigned topic.

Questions must be realistic BSCS university
examination questions.

Prioritize:

- definitions
- important concepts
- explanations
- differences
- working principles
- advantages
- disadvantages
- applications
- examples
- formulas
- components
- types
- classifications
- why/how questions
- comparisons

Do NOT invent information.

Avoid duplicate questions.

Every question MUST have a complete answer.

Answers should normally contain 3 to 6 meaningful
sentences and should be suitable for a university
exam.

Definition questions:
Give definition, explanation, and example when useful.

Comparison questions:
Explain both concepts and their differences.

How questions:
Explain the process logically.

Why questions:
Explain the reasoning.

Formula questions:
Give the formula and explain variables.

RETURN ONLY VALID JSON.

Required structure:

{{
    "questions": [
        {{
            "topic": "Example Topic",
            "question": "Example question?",
            "answer": "A complete exam-ready answer."
        }}
    ]
}}

Generate EXACTLY {number_for_batch} questions.
"""

            response = llm.invoke(
                prompt
            )

            raw_response = (
                response.content
            )

            try:

                parsed = parse_llm_json(
                    raw_response
                )

            except Exception:

                retry_prompt = f"""
Return ONLY valid JSON.

Generate EXACTLY {number_for_batch}
university subjective questions.

ASSIGNED TOPICS:

{json.dumps(batch_topics)}

STUDY MATERIAL:

{batch_context}

Every question requires:

topic
question
answer

Answers must be complete,
factually correct,
material-grounded,
and normally 3 to 6 sentences.

Do not invent information.

Required:

{{
    "questions": [
        {{
            "topic": "Topic",
            "question": "Question?",
            "answer": "Complete answer."
        }}
    ]
}}

Generate EXACTLY {number_for_batch}.
"""

                retry_response = llm.invoke(
                    retry_prompt
                )

                parsed = parse_llm_json(
                    retry_response.content
                )

            if isinstance(
                parsed,
                dict
            ):

                batch_questions = (
                    parsed.get(
                        "questions",
                        []
                    )
                )

            elif isinstance(
                parsed,
                list
            ):

                batch_questions = parsed

            else:

                batch_questions = []

            cleaned_batch = []

            valid_topic_map = {
                topic.lower(): topic
                for topic in unique_batch_topics
            }

            for item in batch_questions:

                if not isinstance(
                    item,
                    dict
                ):

                    continue

                topic = str(
                    item.get(
                        "topic",
                        ""
                    )
                ).strip()

                question = str(
                    item.get(
                        "question",
                        ""
                    )
                ).strip()

                answer = str(
                    item.get(
                        "answer",
                        ""
                    )
                ).strip()

                if not topic:
                    continue

                if not question:
                    continue

                if not answer:
                    continue

                normalized_topic = (
                    topic.lower()
                )

                if normalized_topic not in valid_topic_map:
                    continue

                topic = valid_topic_map[
                    normalized_topic
                ]

                if len(answer.split()) < 25:
                    continue

                cleaned_batch.append(
                    {
                        "topic": topic,
                        "question": question,
                        "answer": answer,
                    }
                )

            unique_questions = []

            seen_questions = set()

            for item in cleaned_batch:

                normalized_question = re.sub(
                    r"\s+",
                    " ",
                    item["question"].lower(),
                ).strip()

                if normalized_question in seen_questions:
                    continue

                seen_questions.add(
                    normalized_question
                )

                unique_questions.append(
                    item
                )

            cleaned_batch = (
                unique_questions
            )

            if len(cleaned_batch) < number_for_batch:

                raise HTTPException(
                    status_code=500,
                    detail=(
                        f"AI generated only "
                        f"{len(cleaned_batch)} valid questions "
                        f"out of {number_for_batch} required."
                    ),
                )

            all_questions.extend(
                cleaned_batch[
                    :number_for_batch
                ]
            )

        final_questions = []

        for index, item in enumerate(
            all_questions,
            start=1,
        ):

            final_questions.append(
                {
                    "question_number":
                        index,

                    "topic":
                        item["topic"],

                    "question":
                        item["question"],

                    "answer":
                        item["answer"],
                }
            )

        if len(final_questions) != (
            request.num_questions
        ):

            raise HTTPException(
                status_code=500,
                detail=(
                    f"Expected "
                    f"{request.num_questions} questions "
                    f"but generated "
                    f"{len(final_questions)}."
                ),
            )

        # Only require coverage of topics assigned to the requested
        # question slots. This allows students to request fewer questions
        # than the total number of topics in the material.
        assigned_topics = {
            topic.strip().casefold()
            for topic in question_plan
        }

        generated_topics = {
            question["topic"].strip().casefold()
            for question in final_questions
        }

        missing_topics = assigned_topics - generated_topics

        if missing_topics:

            raise HTTPException(
                status_code=500,
                detail=(
                    "AI failed to generate questions for all assigned topics. "
                    f"Missing topics: {', '.join(sorted(missing_topics))}"
                ),
            )

        return {

            "material_id":
                request.material_id,

            "material_name":
                request.material_name,

            "difficulty":
                difficulty,

            "total_questions":
                len(final_questions),

            "topics":
                topics,

            "questions":
                final_questions,
        }

    except HTTPException:

        raise

    except Exception as e:

        print(
            "\nSUBJECTIVE GENERATION ERROR:",
            repr(e)
        )

        raise HTTPException(
            status_code=500,
            detail=(
                f"Subjective question generation failed: {str(e)}"
            ),
        )


# =========================================================
# START ADAPTIVE QUIZ
# =========================================================

# =========================================================
# START ADAPTIVE QUIZ
# =========================================================

@app.post("/quiz/start")
def start_quiz(request: QuizStartRequest):

    try:
        # =====================================================
        # VALIDATE MATERIAL ID
        # =====================================================

        material_id = request.material_id.strip()

        if not material_id:
            raise HTTPException(
                status_code=400,
                detail="Material ID is required."
            )

        # =====================================================
        # VALIDATE TOPICS
        # =====================================================

        if not request.topics:
            raise HTTPException(
                status_code=400,
                detail="No topics available for this material."
            )

        # =====================================================
        # VALIDATE QUESTION COUNT
        # =====================================================

        if request.num_questions not in [5, 10, 20, 30, 50]:
            raise HTTPException(
                status_code=400,
                detail="Question count must be 5, 10, 20, 30, or 50."
            )

        # =====================================================
        # VALIDATE DIFFICULTY
        # =====================================================

        difficulty = request.difficulty.strip().lower()

        if difficulty not in ["adaptive", "easy", "medium", "hard"]:
            difficulty = "medium"

        # =====================================================
        # NORMALIZE TOPICS
        # =====================================================

        cleaned_topics = clean_hierarchical_topics(
            request.topics
        )

        if not cleaned_topics:
            raise HTTPException(
                status_code=400,
                detail="No valid topics were found."
            )

        # =====================================================
        # GET ALL AVAILABLE SUBTOPICS
        # =====================================================

        all_subtopics = get_all_subtopics(
            cleaned_topics
        )

        if not all_subtopics:
            raise HTTPException(
                status_code=400,
                detail="No usable subtopics were found."
            )

        # =====================================================
        # CREATE QUIZ ID
        # =====================================================

        quiz_id = f"quiz_{uuid4().hex[:12]}"

        # =====================================================
        # SELECT FIRST MAIN TOPIC
        # =====================================================

        first_group = cleaned_topics[0]

        first_main_topic = first_group["topic"]

        if difficulty == "adaptive":
            prior = get_topic_record(first_main_topic)
            difficulty = choose_starting_difficulty(
                prior["attempts"],
                prior["mastery"],
            )

        first_subtopic = select_subtopic_for_topic(
            first_group,
            {}
        )

        if not first_subtopic:
            first_subtopic = first_main_topic

        # =====================================================
        # DEBUG
        # =====================================================

        print("\n" + "=" * 80)
        print("STARTING ADAPTIVE QUIZ")
        print("=" * 80)

        print("Quiz ID:", quiz_id)
        print("Material ID:", material_id)
        print(
            "Topic groups:",
            json.dumps(cleaned_topics, indent=2)
        )
        print("First main topic:", first_main_topic)
        print("First subtopic:", first_subtopic)
        print("Questions:", request.num_questions)
        print("Difficulty:", difficulty)

        print("=" * 80)

        # =====================================================
        # GENERATE FIRST UNIQUE QUESTION
        # =====================================================

        question = generate_unique_mcq(
            material_id=material_id,
            topic=first_main_topic,
            subtopic=first_subtopic,
            difficulty=difficulty,
            existing_questions=[],
        )

        # =====================================================
        # TRUST ADAPTIVE METADATA
        # =====================================================

        question["topic"] = first_main_topic
        question["subtopic"] = first_subtopic
        question["difficulty"] = difficulty

        # =====================================================
        # CREATE QUIZ SESSION
        # =====================================================

        quiz_sessions[quiz_id] = {
            "quiz_id": quiz_id,
            "material_id": material_id,
            "topic_groups": cleaned_topics,
            "all_subtopics": all_subtopics,
            "main_topic": first_main_topic,
            "subtopics": first_group["subtopics"],
            "current_topic": first_main_topic,
            "current_subtopic": first_subtopic,
            "num_questions": request.num_questions,
            "current_question": 1,
            "difficulty": difficulty,
            "questions": [question],
            "answers": [],
            "completed": False,
        }

        # =====================================================
        # SAFE QUESTION — HIDE CORRECT ANSWER
        # =====================================================

        safe_question = {
            "question": question.get("question", ""),
            "options": question.get("options", {}),
            "topic": first_main_topic,
            "subtopic": first_subtopic,
            "difficulty": difficulty,
        }

        # =====================================================
        # RESPONSE
        # =====================================================

        return {
            "quiz_id": quiz_id,
            "completed": False,

            "quiz_progress": {
                "question_number": 1,
                "total_questions": request.num_questions,
                "percentage_completed": 0,
            },

            "adaptive_state": {
                "current_topic": first_main_topic,
                "current_subtopic": first_subtopic,
                "difficulty": difficulty,
            },

            "question": safe_question,
        }

    except HTTPException:
        raise

    except Exception as e:
        print("\n" + "=" * 80)
        print("QUIZ START ERROR")
        print("=" * 80)
        print(repr(e))
        print("=" * 80)

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


# =========================================================
# SUBMIT ADAPTIVE QUIZ ANSWER
# =========================================================

@app.post("/quiz/answer")
def answer_quiz(request: QuizAnswerRequest):

    try:
        # =====================================================
        # FIND SESSION
        # =====================================================

        quiz = quiz_sessions.get(request.quiz_id)

        if not quiz:
            raise HTTPException(
                status_code=404,
                detail="Quiz session not found."
            )

        # =====================================================
        # CHECK COMPLETION
        # =====================================================

        if quiz.get("completed", False):
            raise HTTPException(
                status_code=400,
                detail="Quiz has already been completed."
            )

        # =====================================================
        # VALIDATE ANSWER
        # =====================================================

        student_answer = request.answer.upper().strip()

        if student_answer not in ["A", "B", "C", "D"]:
            raise HTTPException(
                status_code=400,
                detail="Answer must be A, B, C or D."
            )

        # =====================================================
        # GET CURRENT QUESTION
        # =====================================================

        current_index = len(quiz["answers"])

        if current_index >= len(quiz["questions"]):
            raise HTTPException(
                status_code=400,
                detail="No unanswered question is available."
            )

        current_question = quiz["questions"][current_index]

        # =====================================================
        # CURRENT METADATA
        # =====================================================

        answered_question_text = current_question.get(
            "question", ""
        )

        answered_topic = current_question.get(
            "topic",
            quiz.get("main_topic", "Unknown")
        )

        answered_subtopic = current_question.get(
            "subtopic",
            answered_topic
        )

        answered_difficulty = current_question.get(
            "difficulty",
            quiz.get("difficulty", "medium")
        )

        # =====================================================
        # VALIDATE CORRECT ANSWER
        # =====================================================

        correct_answer = str(
            current_question.get("correct_answer", "")
        ).upper().strip()

        if correct_answer not in ["A", "B", "C", "D"]:
            raise HTTPException(
                status_code=500,
                detail=(
                    "The current quiz question has "
                    "an invalid correct answer."
                )
            )

        # =====================================================
        # CHECK ANSWER
        # =====================================================

        is_correct = student_answer == correct_answer

        # =====================================================
        # GENERATE EXPLANATION
        # =====================================================

        explanation = generate_answer_explanation(
            material_id=quiz["material_id"],
            topic=answered_topic,
            question=current_question.get("question", ""),
            options=current_question.get("options", {}),
            student_answer=student_answer,
            correct_answer=correct_answer,
            source_context=current_question.get(
                "_source_context", ""
            ),
        )

        # =====================================================
        # SAVE ANSWER
        # =====================================================

        quiz["answers"].append(student_answer)
        try:
            learner_update = record_answer(
                topic=answered_topic,
                subtopic=answered_subtopic,
                is_correct=is_correct,
                quiz_id=quiz["quiz_id"],
                material_id=quiz["material_id"],
                difficulty=answered_difficulty,
                question_number=current_index + 1,
                total_questions=quiz["num_questions"],
            )
        except Exception as profile_error:
            print("Could not persist learner model:", repr(profile_error))
            learner_update = {"available": False}

        # =====================================================
        # UPDATE DIFFICULTY
        # =====================================================

        previous_difficulty = quiz.get(
            "difficulty", "medium"
        )

        new_difficulty = next_difficulty(
            previous_difficulty,
            is_correct
        )

        quiz["difficulty"] = new_difficulty

        # =====================================================
        # CALCULATE PERFORMANCE
        # =====================================================

        topic_scores = calculate_topic_performance(
            quiz["questions"],
            quiz["answers"]
        )

        subtopic_scores = calculate_subtopic_performance(
            quiz["questions"],
            quiz["answers"]
        )

        # =====================================================
        # PROGRESS
        # =====================================================

        answered_count = len(quiz["answers"])
        total_questions = quiz["num_questions"]

        # =====================================================
        # CURRENT TOPIC PERFORMANCE
        # =====================================================

        current_topic_performance = topic_scores.get(
            answered_topic,
            {
                "correct": 0,
                "total": 0,
                "percentage": 0,
            }
        )

        current_subtopic_performance = subtopic_scores.get(
            answered_subtopic,
            {
                "correct": 0,
                "total": 0,
                "percentage": 0,
            }
        )

        # =====================================================
        # ANSWERED QUESTION DETAILS
        # =====================================================

        answered_question = {
            "question_number": current_index + 1,
            "question": answered_question_text,
            "options": current_question.get("options", {}),
            "topic": answered_topic,
            "subtopic": answered_subtopic,
            "difficulty": answered_difficulty,
            "your_answer": student_answer,
            "correct_answer": correct_answer,
            "correct": is_correct,
            "explanation": explanation,
        }

        # =====================================================
        # QUIZ COMPLETE
        # =====================================================

        if answered_count >= total_questions:

            result = evaluate_quiz(
                quiz["questions"],
                quiz["answers"]
            )

            quiz["result"] = result
            quiz["completed"] = True
            try:
                complete_quiz(quiz["quiz_id"])
            except Exception as profile_error:
                print("Could not persist quiz completion:", repr(profile_error))

            # -------------------------------------------------
            # STRONG AND WEAK TOPICS
            # -------------------------------------------------

            strong_topics = []
            weak_topics = []

            for topic_name, score in topic_scores.items():

                if score.get("percentage", 0) >= 70:
                    strong_topics.append(topic_name)
                else:
                    weak_topics.append(topic_name)

            # -------------------------------------------------
            # STRONG AND WEAK SUBTOPICS
            # -------------------------------------------------

            strong_subtopics = []
            weak_subtopics = []

            for subtopic_name, score in subtopic_scores.items():

                if score.get("percentage", 0) >= 70:
                    strong_subtopics.append(subtopic_name)
                else:
                    weak_subtopics.append(subtopic_name)

            # -------------------------------------------------
            # FINAL RESPONSE
            # -------------------------------------------------

            return {
                "completed": True,

                "answered_question": answered_question,

                "performance": {
                    "topic": answered_topic,
                    "subtopic": answered_subtopic,
                    "topic_score": current_topic_performance,
                    "subtopic_score": current_subtopic_performance,
                    "topic_scores": topic_scores,
                    "subtopic_scores": subtopic_scores,
                },

                "quiz_progress": {
                    "question_number": answered_count,
                    "total_questions": total_questions,
                    "percentage_completed": 100,
                },

                "adaptive_decision": {
                    "previous_topic": answered_topic,
                    "previous_subtopic": answered_subtopic,
                    "next_topic": None,
                    "next_subtopic": None,
                    "previous_difficulty": previous_difficulty,
                    "next_difficulty": new_difficulty,
                },

                "result": result,
                "learner_model": learner_update,
                "strong_topics": strong_topics,
                "weak_topics": weak_topics,
                "strong_subtopics": strong_subtopics,
                "weak_subtopics": weak_subtopics,
                "final_difficulty": new_difficulty,
            }

        # =====================================================
        # SELECT NEXT MAIN TOPIC
        # =====================================================

        current_main_topic = quiz.get(
            "current_topic",
            answered_topic
        )

        next_main_topic = select_next_main_topic(
            quiz["topic_groups"],
            current_main_topic,
            topic_scores,
            answered_subtopic,
            subtopic_scores,
        )

        if not next_main_topic:
            next_main_topic = current_main_topic

        # =====================================================
        # FIND NEXT TOPIC GROUP
        # =====================================================

        next_group = find_topic_group(
            quiz["topic_groups"],
            next_main_topic,
        )

        if not next_group:
            next_group = {
                "topic": next_main_topic,
                "subtopics": [next_main_topic],
            }

        # =====================================================
        # SELECT NEXT SUBTOPIC
        # =====================================================

        current_subtopic = quiz.get(
            "current_subtopic",
            answered_subtopic
        )

        next_subtopic = select_subtopic_for_topic(
            next_group,
            subtopic_scores,
            current_subtopic=current_subtopic,
        )

        if not next_subtopic:
            next_subtopic = next_main_topic

        # =====================================================
        # DEBUG
        # =====================================================

        print("\n" + "=" * 80)
        print("ADAPTIVE NEXT QUESTION")
        print("=" * 80)

        print("Answered topic:", answered_topic)
        print("Answered subtopic:", answered_subtopic)
        print("Student answer:", student_answer)
        print("Correct:", is_correct)
        print("Previous difficulty:", previous_difficulty)
        print("Next main topic:", next_main_topic)
        print("Next subtopic:", next_subtopic)
        print("Next difficulty:", new_difficulty)

        print("=" * 80)

        # =====================================================
        # GENERATE NEXT UNIQUE QUESTION
        # =====================================================

        next_question = generate_unique_mcq(
            material_id=quiz["material_id"],
            topic=next_main_topic,
            subtopic=next_subtopic,
            difficulty=new_difficulty,
            existing_questions=quiz["questions"],
        )

        # =====================================================
        # TRUSTED METADATA
        # =====================================================

        next_question["topic"] = next_main_topic
        next_question["subtopic"] = next_subtopic
        next_question["difficulty"] = new_difficulty

        # =====================================================
        # UPDATE SESSION
        # =====================================================

        quiz["current_topic"] = next_main_topic
        quiz["current_subtopic"] = next_subtopic

        quiz["subtopics"] = next_group.get(
            "subtopics",
            [next_main_topic]
        )

        # =====================================================
        # SAVE NEXT QUESTION
        # =====================================================

        quiz["questions"].append(next_question)

        quiz["current_question"] = answered_count + 1

        # =====================================================
        # HIDE CORRECT ANSWER
        # =====================================================

        safe_next_question = {
            "question": next_question.get("question", ""),
            "options": next_question.get("options", {}),
            "topic": next_main_topic,
            "subtopic": next_subtopic,
            "difficulty": new_difficulty,
        }

        # =====================================================
        # RESPONSE
        # =====================================================

        return {
            "completed": False,

            "answered_question": answered_question,

            "performance": {
                "topic": answered_topic,
                "subtopic": answered_subtopic,
                "topic_score": current_topic_performance,
                "subtopic_score": current_subtopic_performance,
                "topic_scores": topic_scores,
                "subtopic_scores": subtopic_scores,
            },

            "quiz_progress": {
                "question_number": answered_count,
                "next_question_number": answered_count + 1,
                "total_questions": total_questions,
                "percentage_completed": round(
                    (answered_count / total_questions) * 100,
                    2
                ),
            },

            "adaptive_decision": {
                "previous_topic": answered_topic,
                "previous_subtopic": answered_subtopic,
                "next_topic": next_main_topic,
                "next_subtopic": next_subtopic,
                "previous_difficulty": previous_difficulty,
                "next_difficulty": new_difficulty,
            },

            "learner_model": learner_update,

            "next_question": safe_next_question,
        }

    except HTTPException:
        raise

    except Exception as e:
        print("\n" + "=" * 80)
        print("QUIZ ANSWER ERROR")
        print("=" * 80)
        print("Error:", repr(e))
        print("=" * 80)

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


# =========================================================
# GET QUIZ RESULT
# =========================================================

@app.get("/quiz/result/{quiz_id}")
def get_quiz_result(quiz_id: str):

    try:
        quiz = quiz_sessions.get(quiz_id)

        if not quiz:
            raise HTTPException(
                status_code=404,
                detail="Quiz session not found."
            )

        if not quiz.get("completed", False):
            raise HTTPException(
                status_code=400,
                detail="This quiz has not been completed yet."
            )

        result = evaluate_quiz(
            quiz["questions"],
            quiz["answers"]
        )

        topic_scores = calculate_topic_performance(
            quiz["questions"],
            quiz["answers"]
        )

        subtopic_scores = calculate_subtopic_performance(
            quiz["questions"],
            quiz["answers"]
        )

        strong_topics = []
        weak_topics = []

        for topic, data in topic_scores.items():

            if data.get("percentage", 0) >= 70:
                strong_topics.append(topic)
            else:
                weak_topics.append(topic)

        strong_subtopics = []
        weak_subtopics = []

        for subtopic, data in subtopic_scores.items():

            if data.get("percentage", 0) >= 70:
                strong_subtopics.append(subtopic)
            else:
                weak_subtopics.append(subtopic)

        quiz["result"] = result

        return {
            "quiz_id": quiz_id,
            "material_id": quiz["material_id"],
            "total_questions": quiz["num_questions"],

            "main_topic": quiz.get(
                "main_topic",
                "Unknown"
            ),

            "topic_groups": quiz.get(
                "topic_groups",
                []
            ),

            "result": result,
            "topic_scores": topic_scores,
            "subtopic_scores": subtopic_scores,
            "strong_topics": strong_topics,
            "weak_topics": weak_topics,
            "strong_subtopics": strong_subtopics,
            "weak_subtopics": weak_subtopics,

            "final_difficulty": quiz.get(
                "difficulty",
                "medium"
            ),
        }

    except HTTPException:
        raise

    except Exception as e:
        print("\nQUIZ RESULT ERROR:", repr(e))

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

# =========================================================
# LIVE DASHBOARD API
# Add this below your existing quiz routes in main.py.
# Keep all existing routes and functions unchanged.
# =========================================================

from datetime import datetime, timezone


@app.get("/dashboard")
def get_dashboard():
    """
    Build dashboard metrics from the persistent Bayesian learner profile.
    """
    profile = load_profile()
    totals = profile["overview"]
    recent_activity = profile["recent_activity"]

    topic_mastery = []

    for topic_name, stats in profile["topics"].items():
        percentage = round(float(stats.get("mastery", 0.2)) * 100)

        if percentage >= 85:
            status = "Mastered"
        elif percentage >= 70:
            status = "Proficient"
        elif percentage >= 50:
            status = "Needs Practice"
        else:
            status = "Weak Area"

        topic_mastery.append({
            "title": topic_name,
            "percentage": percentage,
            "accuracy": stats.get("accuracy", 0),
            "correct": stats.get("correct", 0),
            "total": stats.get("total", 0),
            "attempts": stats.get("attempts", 0),
            "status": status,
        })

    topic_mastery.sort(key=lambda item: item["percentage"])

    total_answered = totals["questions_answered"]
    total_correct = totals["correct_answers"]
    accuracy = round((total_correct / total_answered) * 100) if total_answered else 0

    return {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "overview": {
            "accuracy": accuracy,
            "questions_answered": total_answered,
            "completed_quizzes": totals["completed_quizzes"],
            "topics_studied": len(topic_mastery),
        },
        "topic_mastery": topic_mastery,
        "recent_activity": recent_activity[:8],
        "data_status": {
            "quiz_data_available": bool(total_answered),
            "study_time_tracked": False,
            "persistent_storage": True,
            "learner_model": "Bayesian Knowledge Tracing",
        },
    }
