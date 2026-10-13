from langchain_chroma import Chroma
from rag.embeddings import get_embeddings


def get_retriever(collection_name):
    embeddings = get_embeddings()

    vectorstore = Chroma(
        persist_directory="chroma_db",
        collection_name=collection_name,
        embedding_function=embeddings
    )

    return vectorstore.as_retriever(
        search_type="similarity",
        search_kwargs={
            "k": 5
        }
    )