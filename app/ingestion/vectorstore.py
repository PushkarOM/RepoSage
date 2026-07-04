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


def store_documents(docs: list[Document], repo_id: str, job_id: str) -> int:
    """
    Embeds and persists chunks into the shared Chroma collection.
    Before adding, deletes any existing chunks tagged with the same
    repo_id — this makes re-ingestion an upsert instead of a duplicate
    append. job_id is kept only for traceability of which run produced
    a given chunk (useful for debugging failed/retried jobs).
    """
    if not docs:
        return 0

    store = get_vectorstore()

    existing = store.get(where={"repo_id": repo_id})
    existing_ids = existing.get("ids", [])
    if existing_ids:
        store.delete(ids=existing_ids)

    for doc in docs:
        doc.metadata["repo_id"] = repo_id
        doc.metadata["job_id"] = job_id

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
