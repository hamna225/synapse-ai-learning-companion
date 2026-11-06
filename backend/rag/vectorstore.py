import os

from langchain_chroma import Chroma


def create_vectorstore(chunks, embeddings, collection_name):

    vectorstore = Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        persist_directory=os.getenv("SYNAPSE_CHROMA_DB_PATH", "chroma_db"),
        collection_name=collection_name
    )

    return vectorstore
