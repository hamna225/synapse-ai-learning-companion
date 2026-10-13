import json
import os
from pathlib import Path
import threading
from datetime import datetime, timezone


PROFILE_PATH = Path(os.getenv(
    "SYNAPSE_LEARNER_PROFILE_PATH",
    Path(__file__).with_name("learner_state.json"),
))
_PROFILE_LOCK = threading.RLock()
_INITIAL_MASTERY = 0.2


def update_bkt(mastery, is_correct, learn=0.15, guess=0.2, slip=0.1):
    """Apply one Bayesian Knowledge Tracing observation."""
    mastery = min(1.0, max(0.0, float(mastery)))
    if is_correct:
        denominator = mastery * (1 - slip) + (1 - mastery) * guess
        posterior = mastery * (1 - slip) / denominator if denominator else mastery
    else:
        denominator = mastery * slip + (1 - mastery) * (1 - guess)
        posterior = mastery * slip / denominator if denominator else mastery
    return posterior + (1 - posterior) * learn


def _empty_profile():
    return {
        "schema_version": 1,
        "overview": {
            "questions_answered": 0,
            "correct_answers": 0,
            "completed_quizzes": 0,
        },
        "topics": {},
        "subtopics": {},
        "recent_activity": [],
        "history": [],
    }


def load_profile():
    with _PROFILE_LOCK:
        try:
            data = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
            if isinstance(data, dict) and data.get("schema_version") == 1:
                return data
        except (OSError, json.JSONDecodeError):
            pass
        return _empty_profile()


def _save_profile(profile):
    PROFILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    temp_path = PROFILE_PATH.with_suffix(".tmp")
    temp_path.write_text(json.dumps(profile, indent=2), encoding="utf-8")
    temp_path.replace(PROFILE_PATH)


def _update_record(records, name, is_correct):
    record = records.setdefault(name, {
        "mastery": _INITIAL_MASTERY,
        "correct": 0,
        "total": 0,
        "attempts": 0,
    })
    before = float(record.get("mastery", _INITIAL_MASTERY))
    record["mastery"] = update_bkt(before, is_correct)
    record["total"] = int(record.get("total", 0)) + 1
    record["correct"] = int(record.get("correct", 0)) + int(is_correct)
    record["attempts"] = int(record.get("attempts", record["total"] - 1)) + 1
    record["accuracy"] = round(100 * record["correct"] / record["total"], 1)
    record["mastery"] = round(record["mastery"], 6)
    return round(before * 100, 1), round(record["mastery"] * 100, 1)


def record_answer(
    *, topic, subtopic, is_correct, quiz_id, material_id, difficulty,
    question_number, total_questions,
):
    """Persist one answer and update topic/subtopic BKT mastery estimates."""
    topic = str(topic or "Unknown").strip() or "Unknown"
    subtopic = str(subtopic or topic).strip() or topic
    with _PROFILE_LOCK:
        profile = load_profile()
        topic_before, topic_after = _update_record(
            profile["topics"], topic, is_correct
        )
        subtopic_before, subtopic_after = _update_record(
            profile["subtopics"], subtopic, is_correct
        )
        profile["overview"]["questions_answered"] += 1
        profile["overview"]["correct_answers"] += int(is_correct)

        activity = next(
            (item for item in profile["recent_activity"] if item["quiz_id"] == quiz_id),
            None,
        )
        if activity is None:
            activity = {
                "quiz_id": quiz_id,
                "material_id": material_id,
                "topic": topic,
                "completed": False,
                "answered": 0,
                "correct": 0,
                "total_questions": total_questions,
                "difficulty": difficulty,
            }
            profile["recent_activity"].insert(0, activity)
        activity["answered"] += 1
        activity["correct"] += int(is_correct)
        activity["difficulty"] = difficulty

        profile["history"].append({
            "quiz_id": quiz_id,
            "topic": topic,
            "subtopic": subtopic,
            "correct": bool(is_correct),
            "difficulty": difficulty,
            "mastery_before": topic_before,
            "mastery_after": topic_after,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        })
        profile["history"] = profile["history"][-500:]
        profile["recent_activity"] = profile["recent_activity"][:8]
        _save_profile(profile)

    return {
        "topic_mastery": topic_after,
        "subtopic_mastery": subtopic_after,
        "topic_mastery_change": round(topic_after - topic_before, 1),
        "model": "Bayesian Knowledge Tracing",
    }


def complete_quiz(quiz_id):
    with _PROFILE_LOCK:
        profile = load_profile()
        activity = next(
            (item for item in profile["recent_activity"] if item["quiz_id"] == quiz_id),
            None,
        )
        if activity and not activity["completed"]:
            activity["completed"] = True
            profile["overview"]["completed_quizzes"] += 1
            _save_profile(profile)


def get_topic_record(topic):
    return load_profile()["topics"].get(topic, {
        "mastery": _INITIAL_MASTERY,
        "correct": 0,
        "total": 0,
        "attempts": 0,
        "accuracy": 0.0,
    })


def choose_starting_difficulty(attempts, mastery):
    """Choose a first-question level from a returning learner's BKT state."""
    if not attempts:
        return "medium"  # diagnostic starting point
    if float(mastery) < 0.45:
        return "easy"
    if float(mastery) >= 0.80:
        return "hard"
    return "medium"


def analyze_performance(topic_scores):

    weak_topics = []
    strong_topics = []
    practice_topics = []

    for topic, score in topic_scores.items():

        if score < 50:
            weak_topics.append(topic)

        elif score >= 80:
            strong_topics.append(topic)

        else:
            practice_topics.append(topic)

    return {
        "weak_topics": weak_topics,
        "practice_topics": practice_topics,
        "strong_topics": strong_topics
    }
