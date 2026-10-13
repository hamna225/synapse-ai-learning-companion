def evaluate_quiz(questions, student_answers):

    total_questions = len(questions)
    correct = 0
    topic_scores = {}

    for question, student_answer in zip(
        questions,
        student_answers
    ):

        correct_answer = question["correct_answer"]
        topic = question["topic"]

        # Overall score
        if correct_answer.upper() == student_answer.upper():
            correct += 1

        # Create topic record
        if topic not in topic_scores:
            topic_scores[topic] = {
                "correct": 0,
                "total": 0
            }

        topic_scores[topic]["total"] += 1

        if correct_answer.upper() == student_answer.upper():
            topic_scores[topic]["correct"] += 1

    # Calculate topic percentages
    for topic in topic_scores:

        correct_count = topic_scores[topic]["correct"]
        total_count = topic_scores[topic]["total"]

        topic_scores[topic]["percentage"] = (
            correct_count / total_count
        ) * 100

    return {
        "total_questions": total_questions,
        "correct_answers": correct,
        "wrong_answers": total_questions - correct,
        "percentage": (correct / total_questions) * 100,
        "topic_scores": topic_scores
    }