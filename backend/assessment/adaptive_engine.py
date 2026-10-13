# assessment/adaptive_engine.py


# =========================================================
# ADAPTIVE DIFFICULTY
# =========================================================

def next_difficulty(
    current_difficulty,
    is_correct
):
    """
    Adjust difficulty based on the student's answer.

    Correct answer:
        easy   -> medium
        medium -> hard
        hard   -> hard

    Wrong answer:
        hard   -> medium
        medium -> easy
        easy   -> easy
    """

    difficulty = str(
        current_difficulty
    ).lower().strip()

    if difficulty not in [
        "easy",
        "medium",
        "hard"
    ]:
        difficulty = "medium"

    if is_correct:

        if difficulty == "easy":
            return "medium"

        if difficulty == "medium":
            return "hard"

        return "hard"

    else:

        if difficulty == "hard":
            return "medium"

        if difficulty == "medium":
            return "easy"

        return "easy"


# =========================================================
# MAIN TOPIC PERFORMANCE
# =========================================================

def calculate_topic_performance(
    questions,
    answers
):
    """
    Calculate overall performance for the MAIN topic.

    Example:

    Theory of Automata
        correct: 6
        total: 10
        percentage: 60
    """

    topic_scores = {}

    for question, answer in zip(
        questions,
        answers
    ):

        # -------------------------------------------------
        # IMPORTANT:
        # Always use the main topic.
        # -------------------------------------------------

        topic = question.get(
            "topic",
            "Unknown"
        )

        topic = str(
            topic
        ).strip()

        if not topic:
            topic = "Unknown"

        correct_answer = question.get(
            "correct_answer"
        )

        if topic not in topic_scores:

            topic_scores[topic] = {
                "correct": 0,
                "total": 0
            }

        topic_scores[topic]["total"] += 1

        if (
            correct_answer
            and answer
            and str(correct_answer).upper().strip()
            == str(answer).upper().strip()
        ):

            topic_scores[topic]["correct"] += 1

    # -----------------------------------------------------
    # CALCULATE PERCENTAGES
    # -----------------------------------------------------

    for topic, data in topic_scores.items():

        if data["total"] > 0:

            data["percentage"] = round(
                (
                    data["correct"]
                    / data["total"]
                ) * 100,
                2
            )

        else:

            data["percentage"] = 0

    return topic_scores


# =========================================================
# SUBTOPIC PERFORMANCE
# =========================================================

def calculate_subtopic_performance(
    questions,
    answers
):
    """
    Calculate performance for each subtopic.

    Example:

    {
        "Formal vs Informal Languages": {
            "correct": 2,
            "total": 3,
            "percentage": 66.67
        }
    }
    """

    subtopic_scores = {}

    for question, answer in zip(
        questions,
        answers
    ):

        subtopic = question.get(
            "subtopic"
        )

        if not subtopic:

            # Backward compatibility
            subtopic = question.get(
                "topic",
                "Unknown"
            )

        subtopic = str(
            subtopic
        ).strip()

        if not subtopic:

            subtopic = "Unknown"

        correct_answer = question.get(
            "correct_answer"
        )

        if subtopic not in subtopic_scores:

            subtopic_scores[subtopic] = {
                "correct": 0,
                "total": 0
            }

        subtopic_scores[subtopic]["total"] += 1

        if (
            correct_answer
            and answer
            and str(correct_answer).upper().strip()
            == str(answer).upper().strip()
        ):

            subtopic_scores[subtopic]["correct"] += 1

    # -----------------------------------------------------
    # CALCULATE PERCENTAGES
    # -----------------------------------------------------

    for subtopic, data in subtopic_scores.items():

        if data["total"] > 0:

            data["percentage"] = round(
                (
                    data["correct"]
                    / data["total"]
                ) * 100,
                2
            )

        else:

            data["percentage"] = 0

    return subtopic_scores


# =========================================================
# SELECT NEXT SUBTOPIC
# =========================================================
def select_next_subtopic(
    subtopics,
    subtopic_scores,
    current_subtopic=None
):
    """
    Select the next subtopic.

    Rules:
    1. First choose a subtopic that has not been attempted.
    2. Do not immediately repeat the current subtopic.
    3. If all subtopics were attempted, choose the weakest one.
    """

    if not subtopics:
        return None

    # Remove duplicate subtopics
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
        return None

    # =====================================================
    # STEP 1:
    # Find an unattempted subtopic
    # =====================================================

    for subtopic in cleaned_subtopics:

        if subtopic not in subtopic_scores:

            # Don't select the subtopic we just answered
            if (
                current_subtopic is None
                or subtopic.lower()
                != str(current_subtopic).lower().strip()
            ):
                return subtopic

    # =====================================================
    # STEP 2:
    # All subtopics were attempted
    # Choose the weakest DIFFERENT subtopic
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

        weakest_subtopic = min(
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

        return weakest_subtopic

    # =====================================================
    # STEP 3:
    # Only one subtopic exists
    # =====================================================

    return cleaned_subtopics[0]


# =========================================================
# BACKWARD COMPATIBILITY
# =========================================================

def select_next_topic(
    topics,
    topic_scores
):
    """
    Backward-compatible wrapper.
    """

    return select_next_subtopic(
        topics,
        topic_scores
    )

# =========================================================
# BACKWARD COMPATIBILITY
# =========================================================

def select_next_topic(
    topics,
    topic_scores
):
    """
    Backward-compatible wrapper.

    This function is kept so older code does not break.

    New adaptive quiz code should use:

        select_next_subtopic()
    """

    return select_next_subtopic(
        topics,
        topic_scores
    )