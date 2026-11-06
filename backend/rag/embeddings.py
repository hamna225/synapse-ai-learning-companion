from functools import lru_cache

from langchain_huggingface import HuggingFaceEmbeddings


@lru_cache(maxsize=1)
def get_embeddings():

    embeddings = HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-MiniLM-L6-v2"
    )

    return embeddings
