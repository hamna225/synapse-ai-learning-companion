import os

from dotenv import load_dotenv
from langchain_groq import ChatGroq

from rag.retriever import get_retriever


load_dotenv()


def get_llm(reasoning_effort=None):
    return ChatGroq(
        model="openai/gpt-oss-20b",
        temperature=0,
        max_tokens=4096,
        **({"reasoning_effort": reasoning_effort} if reasoning_effort else {}),
        api_key=os.getenv("GROQ_API_KEY")
    )


def get_tutor(collection_name):
    llm = get_llm()

    retriever = get_retriever(collection_name)

    return llm, retriever

