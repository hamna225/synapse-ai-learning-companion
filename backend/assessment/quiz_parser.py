import re


def parse_quiz(text):

    questions = []

    blocks = re.split(r"QUESTION \d+:", text)

    for block in blocks:

        if not block.strip():
            continue

        question_match = re.search(
            r"(.*?)\n\nOPTIONS:",
            block,
            re.DOTALL
        )

        options_match = re.search(
            r"OPTIONS:\n"
            r"A\. (.*?)\n"
            r"B\. (.*?)\n"
            r"C\. (.*?)\n"
            r"D\. (.*?)\n\n",
            block,
            re.DOTALL
        )

        answer_match = re.search(
            r"CORRECT ANSWER:\n([A-D])",
            block
        )

        topic_match = re.search(
            r"TOPIC:\n(.*?)\n",
            block
        )

        difficulty_match = re.search(
            r"DIFFICULTY:\n(.*?)\n",
            block
        )

        if (
            question_match
            and options_match
            and answer_match
            and topic_match
            and difficulty_match
        ):

            questions.append({
                "question": question_match.group(1).strip(),

                "options": [
                    options_match.group(1).strip(),
                    options_match.group(2).strip(),
                    options_match.group(3).strip(),
                    options_match.group(4).strip()
                ],

                "correct_answer": answer_match.group(1).strip(),

                "topic": topic_match.group(1).strip(),

                "difficulty": difficulty_match.group(1).strip()
            })

    return questions