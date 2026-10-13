import json
import re

from agents.tutor_agent import get_llm
from rag.retriever import get_retriever


# =========================================================
# LLM RESPONSE EXTRACTION
# =========================================================

def extract_llm_text(response):
    """
    Extract only the actual final response from the LLM.

    IMPORTANT:
    Do NOT use reasoning_content as the final answer.
    Some reasoning models may return:
        content = ""
        reasoning_content = "..."
    In that case we return an empty string so the caller
    can handle the failure safely.
    """

    print("\nLLM response type:", type(response))
    print("LLM response:", response)

    content = getattr(response, "content", response)

    if isinstance(content, str):
        text = content.strip()

    elif isinstance(content, list):
        parts = []

        for item in content:
            if isinstance(item, str):
                parts.append(item)

            elif isinstance(item, dict):
                if "text" in item:
                    parts.append(str(item["text"]))

                elif "output_text" in item:
                    parts.append(str(item["output_text"]))

        text = "\n".join(parts).strip()

    else:
        text = str(content).strip()

    print("Extracted content length:", len(text))

    if text:
        print("Extracted LLM text:")
        print(text)

    return text


# =========================================================
# JSON PARSER
# =========================================================

def parse_json_response(content):
    """
    Safely extract JSON from an LLM response.
    """

    if not content:
        raise ValueError(
            "LLM returned an empty final response."
        )

    text = content.strip()

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
    # Find JSON object inside response
    # -----------------------------------------------------

    object_match = re.search(
        r"\{.*\}",
        text,
        re.DOTALL,
    )

    if object_match:
        candidate = object_match.group(0)

        try:
            return json.loads(candidate)

        except json.JSONDecodeError:
            pass

    # -----------------------------------------------------
    # Find JSON array inside response
    # -----------------------------------------------------

    array_match = re.search(
        r"\[.*\]",
        text,
        re.DOTALL,
    )

    if array_match:
        candidate = array_match.group(0)

        try:
            return json.loads(candidate)

        except json.JSONDecodeError:
            pass

    raise ValueError(
        "Could not parse valid JSON from LLM response."
    )


# =========================================================
# NORMALIZE MCQ
# =========================================================

def normalize_mcq(question):
    """
    Validate and normalize generated MCQ structure.
    """

    if not isinstance(question, dict):
        raise ValueError(
            "Generated MCQ is not a JSON object."
        )

    required_fields = [
        "question",
        "options",
        "correct_answer",
    ]

    for field in required_fields:
        if field not in question:
            raise ValueError(
                f"Generated MCQ is missing field: {field}"
            )

    # -----------------------------------------------------
    # Question
    # -----------------------------------------------------

    question_text = str(
        question.get("question", "")
    ).strip()

    if not question_text:
        raise ValueError(
            "Generated MCQ has an empty question."
        )

    # -----------------------------------------------------
    # Options
    # -----------------------------------------------------

    options = question.get("options")

    if not isinstance(options, dict):
        raise ValueError(
            "Generated MCQ options must be an object."
        )

    normalized_options = {}

    for key in ["A", "B", "C", "D"]:

        if key not in options:
            raise ValueError(
                f"Generated MCQ is missing option {key}."
            )

        value = str(
            options[key]
        ).strip()

        if not value:
            raise ValueError(
                f"Generated MCQ option {key} is empty."
            )

        normalized_options[key] = value

    # -----------------------------------------------------
    # Correct answer
    # -----------------------------------------------------

    correct_answer = str(
        question.get("correct_answer", "")
    ).strip().upper()

    # Handle formats like:
    # "A"
    # "A)"
    # "(A)"
    # "Option A"

    match = re.search(
        r"\b([ABCD])\b",
        correct_answer,
    )

    if match:
        correct_answer = match.group(1)

    correct_answer = correct_answer.replace(
        ")",
        "",
    ).replace(
        "(",
        "",
    ).strip()

    if correct_answer not in ["A", "B", "C", "D"]:
        raise ValueError(
            f"Invalid correct_answer: {correct_answer}"
        )

    # -----------------------------------------------------
    # Final normalized object
    # -----------------------------------------------------

    normalized = {
        "question": question_text,
        "options": normalized_options,
        "correct_answer": correct_answer,
    }

    # Preserve optional fields
    for field in [
        "topic",
        "subtopic",
        "difficulty",
    ]:
        if field in question:
            normalized[field] = question[field]

    return normalized


# =========================================================
# GENERATE MCQ
# =========================================================


def generate_mcq(
    material_id: str,
    topic: str,
    subtopic: str = None,
    difficulty: str = "medium",
    previous_questions=None,
):
    """
    Generate and validate one MCQ from uploaded learning material.
    Retry when the LLM returns empty content or invalid JSON.
    """

    print("\n" + "=" * 60)
    print("GENERATING MCQ")
    print("=" * 60)

    print("Material ID:", material_id)
    print("Topic:", topic)
    print("Subtopic:", subtopic)
    print("Difficulty:", difficulty)

    # 1. Retrieve learning material
    retriever = get_retriever(material_id)

    if retriever is None:
        raise ValueError(
            f"Could not create retriever for material: {material_id}"
        )

    query = f"{topic} {subtopic or ''} definitions concepts examples rules"
    docs = retriever.invoke(query)

    context_parts = []

    for doc in (docs or [])[:5]:
        content = getattr(doc, "page_content", "")
        if content and content.strip():
            context_parts.append(content.strip())

    context = "\n\n".join(context_parts).strip()

    if not context:
        raise ValueError(
            "No relevant source context found for MCQ generation."
        )

    context = context[:7000]

    previous_questions_text = "\n".join(
        f"- {question}"
        for question in (previous_questions or [])[-12:]
        if question
    ) or "None"

    # 2. Get LLM
    # Keep reasoning-model output focused on the JSON quiz item so its
    # internal reasoning does not consume the completion token budget.
    llm = get_llm(reasoning_effort="low")

    # 3. Build a concise prompt
    prompt = f"""
Generate exactly ONE multiple-choice question using only
the learning material provided.

Topic: {topic}
Subtopic: {subtopic or "General"}
Difficulty: {difficulty}

Questions already asked for this material:
{previous_questions_text}

Learning material:
{context}

Return one valid JSON object only, with no markdown:

{{
  "question": "Question text",
  "options": {{
    "A": "Option A",
    "B": "Option B",
    "C": "Option C",
    "D": "Option D"
  }},
  "correct_answer": "A"
}}

Requirements:
- Exactly four non-empty options.
- Exactly one correct option.
- correct_answer must be A, B, C, or D.
- The question must be answerable from the supplied material.
- Test a different fact or learning objective from the questions already asked.
- Do not repeat or paraphrase a question already asked; use another relevant point from the material.
- Do not include explanations or text outside the JSON.
"""

    # 4. Retry empty or invalid responses
    last_error = None

    for attempt in range(1, 4):
        try:
            print(f"MCQ generation attempt {attempt}/3")

            response = llm.invoke(prompt)
            content = extract_llm_text(response)

            if not content:
                raise ValueError(
                    "LLM returned empty final content."
                )

            parsed_question = parse_json_response(content)
            question = normalize_mcq(parsed_question)

            # 5. Add trusted server-side metadata
            question["topic"] = topic
            question["subtopic"] = subtopic or ""
            question["difficulty"] = difficulty
            question["_source_context"] = context

            print("MCQ generated and validated successfully.")

            return question

        except Exception as exc:
            last_error = exc

            print(
                f"MCQ attempt {attempt} failed: "
                f"{type(exc).__name__}: {exc}"
            )

    # 6. Fail clearly if every attempt fails
    raise ValueError(
        "Could not generate a valid MCQ after 3 attempts. "
        f"Last error: {last_error}"
    )


    # =====================================================
    # LLM CALL
    # =====================================================

    response = llm.invoke(prompt)

    content = extract_llm_text(response)

    # =====================================================
    # EMPTY RESPONSE PROTECTION
    # =====================================================

    if not content:

        print("\nWARNING: LLM returned empty final content.")

        # IMPORTANT:
        # reasoning_content is NOT used as the answer.
        reasoning = getattr(
            response,
            "additional_kwargs",
            {},
        ).get(
            "reasoning_content",
            "",
        )

        if reasoning:
            print(
                "Reasoning content exists, "
                "but it will NOT be used as MCQ output."
            )

        raise ValueError(
            "LLM returned an empty final response while generating the MCQ."
        )

    # =====================================================
    # PARSE JSON
    # =====================================================

    question = parse_json_response(
        content
    )

    # =====================================================
    # NORMALIZE / VALIDATE
    # =====================================================

    question = normalize_mcq(
        question
    )

    # =====================================================
    # ADD SERVER-SIDE METADATA
    # =====================================================

    question["topic"] = topic

    question["subtopic"] = (
        subtopic or ""
    )

    question["difficulty"] = difficulty

    # Keep source context so that the answer explanation
    # can use exactly the same retrieved material.
    question["_source_context"] = context

    print("\nGenerated MCQ successfully:")
    print(
        json.dumps(
            {
                "question": question["question"],
                "options": question["options"],
                "correct_answer": question["correct_answer"],
                "topic": question["topic"],
                "subtopic": question["subtopic"],
                "difficulty": question["difficulty"],
            },
            indent=2,
            ensure_ascii=False,
        )
    )

    return question


# =========================================================
# ANSWER EXPLANATION
# =========================================================


def generate_answer_explanation(
    material_id: str,
    topic: str,
    question: str,
    options: dict,
    student_answer: str,
    correct_answer: str,
    source_context: str = "",
):
    """
    Generate a reliable, source-grounded MCQ explanation.
    """

    try:
        llm = get_llm()

        # 1. Normalize the options.
        options = options if isinstance(options, dict) else {}

        normalized_options = {
            key: str(options.get(key, "")).strip()
            for key in ["A", "B", "C", "D"]
        }

        # 2. Normalize answer labels or full option text.
        def normalize_answer(value):
            value = str(value or "").strip()

            # Match A, (A), A), Option A, etc.
            match = re.fullmatch(
                r"\s*(?:option\s*)?[\(\[]?([ABCD])[\)\]]?\.?\s*",
                value,
                flags=re.IGNORECASE,
            )

            if match:
                return match.group(1).upper()

            # Support a frontend that sends the option text.
            for label, text in normalized_options.items():
                if (
                    text
                    and value.casefold() == text.casefold()
                ):
                    return label

            return None

        student_label = normalize_answer(student_answer)
        correct_label = normalize_answer(correct_answer)

        if correct_label is None:
            raise ValueError(
                f"Invalid correct answer format: {correct_answer}"
            )

        if student_label is None:
            raise ValueError(
                f"Invalid student answer format: {student_answer}"
            )

        correct_text = normalized_options[correct_label]
        student_text = normalized_options[student_label]

        is_correct = student_label == correct_label

        # 3. Retrieve the learning material when necessary.
        if not source_context:
            retriever = get_retriever(material_id)

            if retriever is not None:
                docs = retriever.invoke(
                    f"{topic} {question} "
                    "definitions examples rules reasoning"
                )

                source_context = "\n\n".join(
                    getattr(doc, "page_content", "")
                    for doc in (docs or [])[:5]
                )

        source_context = (source_context or "")[:7000]

        # 4. Provide a safe fallback if context is unavailable.
        if not source_context.strip():
            return (
                f"{'Correct!' if is_correct else 'Incorrect.'} "
                f"The correct answer is {correct_label}: "
                f"{correct_text}. "
                "The learning material was unavailable, so "
                "a detailed explanation could not be verified."
            )

        # 5. Generate an explanation with explicit answer labels.
        prompt = f"""
You are a precise computer science tutor.

Explain the student's answer to the exact MCQ below.

TOPIC:
{topic}

QUESTION:
{question}

OPTIONS:
A: {normalized_options["A"]}
B: {normalized_options["B"]}
C: {normalized_options["C"]}
D: {normalized_options["D"]}

STUDENT SELECTED:
Label: {student_label}
Text: {student_text}

VERIFIED CORRECT ANSWER FROM THE QUIZ:
Label: {correct_label}
Text: {correct_text}

STUDENT STATUS:
{"CORRECT" if is_correct else "INCORRECT"}

SOURCE MATERIAL:
{source_context}

STRICT INSTRUCTIONS:

1. The verified correct-answer label above is authoritative.
   Never replace it with another option.
2. Read the question carefully. Pay special attention to
   NOT, EXCEPT, FALSE, INCORRECT, and DOES NOT BELONG.
3. Answer the exact question, not a different question.
4. Explain why the correct option satisfies the question.
5. Explain the student's selected option accurately.
6. For string-language questions, count the symbols explicitly
   and compare the length with the language's condition.
7. For calculations, show the important steps.
8. Do not claim the student made a particular mistake unless
   the question and their selection support that conclusion.
9. Use the source material and established definitions.
10. If the source does not support a claim, acknowledge the
    limitation instead of inventing facts.
11. Use clear beginner-friendly language.
12. Give a useful explanation, normally 4-7 sentences.
13. Do not generate a new question or change the options.
14. Do not contradict the verified correct-answer label.

Return only the explanation text.
"""

        response = llm.invoke(prompt)
        content = extract_llm_text(response)

        if not content:
            raise ValueError(
                "LLM returned an empty explanation."
            )

        # The status and correct option come from Python,
        # not from the LLM's interpretation.
        if is_correct:
            prefix = (
                f"Correct! Your answer is "
                f"{student_label}: {correct_text}."
            )
        else:
            prefix = (
                f"Not quite. You selected "
                f"{student_label}: {student_text}. "
                f"The correct answer is "
                f"{correct_label}: {correct_text}."
            )

        return f"{prefix}\n\n{content}"

    except Exception as e:
        print(
            "Explanation generation error:",
            repr(e),
        )

        return (
            f"The correct answer is {correct_answer}. "
            "The detailed explanation could not be generated."
        )
