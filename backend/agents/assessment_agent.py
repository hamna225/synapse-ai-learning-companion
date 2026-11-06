from agents.model_provider import get_text_model
from rag.retriever import get_retriever


def get_assessment_agent():
    llm = get_text_model(temperature=0.2)

    retriever = get_retriever()

    return llm, retriever


def generate_quiz(llm, retriever, topic, difficulty="easy"):

    results = retriever.invoke(topic)

    context = "\n\n".join(
        doc.page_content
        for doc in results
    )

    prompt = f"""
You are an adaptive learning assessment agent.

Create 3 multiple-choice questions from the provided course material.

Topic:
{topic}

Difficulty:
{difficulty}

Use ONLY the provided course material.

Return the result in exactly this format:

QUESTION 1:
<question>

OPTIONS:
A. <option>
B. <option>
C. <option>
D. <option>

CORRECT ANSWER:
<A/B/C/D>

TOPIC:
<topic>

DIFFICULTY:
<easy/medium/hard>


QUESTION 2:
...

QUESTION 3:
...

Course Material:
{context}
"""

    response = llm.invoke(prompt)

    return response.content
