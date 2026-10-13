from assessment.adaptive_engine import next_difficulty
from assessment.evaluator import evaluate_quiz
from assessment.quiz_parser import parse_quiz
from student_analytics.learner_profile import analyze_performance
from student_analytics.recommendation import generate_recommendations


def test_next_difficulty_adapts_to_answer():
    assert next_difficulty("easy", True) == "medium"
    assert next_difficulty("hard", False) == "medium"


def test_parse_quiz_extracts_question_fields():
    quiz_text = """QUESTION 1:
What is 2 + 2?

OPTIONS:
A. 3
B. 4
C. 5
D. 6

CORRECT ANSWER:
B
TOPIC:
Arithmetic
DIFFICULTY:
easy
"""

    parsed = parse_quiz(quiz_text)

    assert len(parsed) == 1
    assert parsed[0]["question"] == "What is 2 + 2?"
    assert parsed[0]["options"] == ["3", "4", "5", "6"]
    assert parsed[0]["correct_answer"] == "B"


def test_evaluate_quiz_and_recommendations():
    questions = [
        {"correct_answer": "A", "topic": "Arrays"},
        {"correct_answer": "B", "topic": "Arrays"},
    ]

    result = evaluate_quiz(questions, ["A", "A"])

    assert result["total_questions"] == 2
    assert result["correct_answers"] == 1
    assert result["topic_scores"]["Arrays"]["percentage"] == 50

    analysis = analyze_performance({"Arrays": 50, "Trees": 90})
    recommendations = generate_recommendations(analysis)

    assert analysis["practice_topics"] == ["Arrays"]
    assert any(item["topic"] == "Trees" for item in recommendations)
