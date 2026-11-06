from agents.model_provider import get_text_model
from rag.retriever import get_retriever

def get_llm(reasoning_effort=None):
    return get_text_model(reasoning_effort=reasoning_effort)


def get_tutor(collection_name):
    llm = get_llm()

    retriever = get_retriever(collection_name)

    return llm, retriever

