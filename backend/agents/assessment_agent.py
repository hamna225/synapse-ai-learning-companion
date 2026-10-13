import os
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from rag.retriever import get_retriever

load_dotenv()


def get_assessment_agent():

    llm = ChatGroq(
        model="openai/gpt-oss-20b",
        temperature=0.2,
        api_key=os.getenv("GROQ_API_KEY")
    )

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