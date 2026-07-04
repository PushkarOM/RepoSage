from langchain_chroma import Chroma
from langchain_core.documents import Document

from app.core.config import settings
from app.core.embeddings import get_embedding_function

COLLECTION_NAME = "reposage"


def get_vectorstore() -> Chroma:
    """
    Returns a Chroma vectorstore instance backed by the configured
    embedding function and persisted to disk. Called both when writing
    (ingestion) and reading (agent tool queries), so it's the single
    source of truth for how we talk to Chroma.
    """
    return Chroma(
        collection_name=COLLECTION_NAME,
        embedding_function=get_embedding_function(),
        persist_directory=settings.chroma_persist_dir,
    )


def store_documents(docs: list[Document], job_id: str) -> int:
    """
    Embeds and persists a list of chunks into the shared Chroma collection.
    Tags every chunk with job_id so a future re-ingestion or multi-repo
    setup can filter/delete by job without touching other repos' data.
    """
    if not docs:
        return 0

    for doc in docs:
        doc.metadata["job_id"] = job_id

    store = get_vectorstore()
    store.add_documents(docs)
    return len(docs)


def search(query: str, k: int = 5, doc_type: str | None = None) -> list[Document]:
    """
    Similarity search over the collection. doc_type ("code" | "doc")
    filters via metadata instead of needing separate collections —
    this is the query-time equivalent of the collection split we
    decided against.
    """
    store = get_vectorstore()
    filter_dict = {"type": doc_type} if doc_type else None
    return store.similarity_search(query, k=k, filter=filter_dict)
