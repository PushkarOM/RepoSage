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
    if not docs:
        return 0

    store = get_vectorstore()

    # Find old chunks (if any) BEFORE inserting new ones, but don't delete
    # yet -- deleting first, then inserting, has a real failure window: if
    # the process dies between the two steps (e.g. a container restart
    # mid-ingestion), the repo ends up with zero chunks instead of just
    # stale ones. Inserting first means the worst case if interrupted is
    # "briefly has both old and new data," never "has nothing."
    existing = store.get(where={"repo_id": repo_id})
    old_ids = existing.get("ids", [])

    for doc in docs:
        doc.metadata["repo_id"] = repo_id
        doc.metadata["job_id"] = job_id

    store.add_documents(docs)

    if old_ids:
        store.delete(ids=old_ids)

    return len(docs)

# backend/app/ingestion/vectorstore.py -- add
async def expand_query(query: str) -> list[str]:
    """
    Generates a couple of alternative phrasings of the query via the LLM,
    to catch relevant chunks a single vague/colloquial question might miss
    entirely -- the multi-query retrieval pattern. Fails gracefully (empty
    list) rather than blocking search entirely if the LLM call errors.
    """
    from app.core.llm import get_chat_model
    model = get_chat_model()

    prompt = (
        "Generate 2 alternative search queries to help find relevant code or "
        "documentation for this question, especially if it's vague. Focus on "
        "specific technical terms, function/file names, or concepts likely to "
        "appear in code. Return ONLY the 2 queries, one per line, no numbering.\n\n"
        f"Question: {query}"
    )
    try:
        response = await model.ainvoke([{"role": "user", "content": prompt}])
        content = response.content
        if isinstance(content, list):
            content = "".join(b.get("text", "") for b in content if isinstance(b, dict))
        return [line.strip() for line in content.strip().split("\n") if line.strip()][:2]
    except Exception:
        return []


async def multi_search(query: str, k: int = 5, doc_type: str | None = None, repo_id: str | None = None) -> list[Document]:
    """
    Searches with the original query plus a couple of LLM-generated
    expansions, merging and deduping results (by source + chunk_index)
    rather than just using one. Capped at k total results even though
    multiple queries can surface more candidates.
    """
    queries = [query] + await expand_query(query)
    seen = set()
    merged = []

    for q in queries:
        for r in search(q, k=k, doc_type=doc_type, repo_id=repo_id):
            key = (r.metadata.get("source"), r.metadata.get("chunk_index"))
            if key not in seen:
                seen.add(key)
                merged.append(r)

    return merged[:k]



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
