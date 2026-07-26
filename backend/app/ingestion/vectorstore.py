import chromadb
from langchain_chroma import Chroma
from langchain_core.documents import Document

from app.core.config import settings
from app.core.embeddings import get_embedding_function

COLLECTION_NAME = "reposage"


def get_vectorstore() -> Chroma:
    """
    Connects to a standalone Chroma server over the network, rather than
    opening an embedded, file-based client directly. The API and worker
    are separate processes that both need to read/write vector data --
    Chroma's embedded client isn't safe for multiple processes to open
    the same on-disk files concurrently, which is what caused the
    intermittent "Error finding id" corruption. Routing both processes
    through one Chroma server process, which alone owns the actual
    files, fixes that at the source rather than papering over it.
    """
    client = chromadb.HttpClient(host=settings.chroma_host, port=settings.chroma_port)
    return Chroma(
        client=client,
        collection_name=COLLECTION_NAME,
        embedding_function=get_embedding_function(),
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

def search(query: str, k: int = 5, doc_type: str | None = None, repo_id: str | None = None) -> list[Document]:
    """
    Similarity search over the collection, optionally filtered by
    doc_type ("code"/"doc") and/or repo_id. repo_id scoping matters once
    more than one repo is ingested -- without it, results from every
    ingested repo would be mixed together indiscriminately.
    """
    store = get_vectorstore()

    conditions = []
    if doc_type:
        conditions.append({"type": doc_type})
    if repo_id:
        conditions.append({"repo_id": repo_id})

    if not conditions:
        filter_dict = None
    elif len(conditions) == 1:
        filter_dict = conditions[0]
    else:
        filter_dict = {"$and": conditions}

    return store.similarity_search(query, k=k, filter=filter_dict)
