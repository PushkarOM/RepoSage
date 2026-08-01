import re
import chromadb
from langchain_chroma import Chroma
from langchain_core.documents import Document
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from rank_bm25 import BM25Okapi

from app.core.config import settings
from app.core.embeddings import get_embedding_function

COLLECTION_NAME = "reposage"

# --- Hybrid search (BM25 + vector) constants ---
# Tokenization for BM25: lowercase + split on non-alphanumeric. Crude but
# sufficient for source code + prose at our chunk sizes; the alternative
# (TreebankWordTokenizer, stop-word removal) costs more in latency than
# it returns for retrieval quality here.
_BM25_TOKEN_RE = re.compile(r"[A-Za-z0-9_]+")
    
# Reciprocal rank fusion constant. k=60 is the value from the original
# Cormack et al. (2009) paper and the de-facto default in every hybrid
# retrieval reference since -- changing it is a knob, not a bug to chase.
_RRF_K = 60

# Per-list weights for reciprocal rank fusion. Vector similarity leads
# at full weight (the embedding model captures "how does X work" well),
# and BM25 contributes at 0.7 to rescue keyword-misses (e.g. "what is
# this repo about") without overpowering the semantic ranking on
# queries where BM25 latches onto spurious keyword matches (chunks that
# contain query terms verbatim but aren't the right answer -- a common
# shape in repo corpora). 0.7 was chosen after a 1.5:1.0 attempt hurt
# MRR by letting BM25 dominate on those spurious matches; if the eval
# artifact still shows regression, drop to 0.5.
VECTOR_WEIGHT = 1.0
BM25_WEIGHT = 0.7

# Routing thresholds for _should_use_hybrid. Short / exact-path queries
# skip BM25 entirely: the per-call BM25 cost (even cached) isn't worth
# it when the query is already a near-perfect vector hit on its own.
_MAX_VECTOR_ONLY_TOKENS = 3
_FILE_PATH_RE = re.compile(
    r"[/\\][\w./-]+\.\w{1,5}"           # /path/to/file.py
    r"|\b[\w_-]+\.(?:py|md|ts|tsx|js|jsx|go|rs|java|rb)\b",  # bare filename
    re.IGNORECASE,
)

# Per-repo BM25 index cache. Building the index is O(N) over every chunk
# in the repo, not something to repeat on every search_codebase call.
# Lives in-process; a worker restart re-warms it on the first query, same
# pattern as the embedding model warm-up at startup.
_BM25_INDEX_CACHE: dict[str, "BM25Okapi"] = {}
_BM25_DOCS_CACHE: dict[str, list[Document]] = {}


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


# --- Hybrid search (BM25 + vector) ---

def _build_bm25_index(repo_id: str) -> tuple["BM25Okapi", list[Document]]:
    """
    Loads all chunks for a repo from Chroma and tokenizes them for BM25.
    Cached per repo_id -- building the index is O(N) over every chunk
    in the repo, not something to repeat on every search_codebase call.
    rank_bm25 is imported lazily so the import cost is paid only if a
    hybrid query actually fires (vector-only paths never touch it).
    """
    if repo_id in _BM25_INDEX_CACHE:
        return _BM25_INDEX_CACHE[repo_id], _BM25_DOCS_CACHE[repo_id]

    from rank_bm25 import BM25Okapi

    store = get_vectorstore()
    raw = store.get(where={"repo_id": repo_id})
    docs = [
        Document(page_content=text, metadata=meta)
        for text, meta in zip(raw.get("documents", []), raw.get("metadatas", []))
    ]

    tokenized = [_BM25_TOKEN_RE.findall(d.page_content.lower()) for d in docs]
    index = BM25Okapi(tokenized)

    _BM25_INDEX_CACHE[repo_id] = index
    _BM25_DOCS_CACHE[repo_id] = docs
    return index, docs


def _reciprocal_rank_fusion(
    ranked_lists: list[list[Document]],
    weights: list[float] | None = None,
    k: int = _RRF_K,
) -> list[Document]:
    """
    Fuses ranked lists from different retrievers via weighted reciprocal
    rank fusion. Each doc's final score = sum of weight_i / (k + rank)
    across every list it appears in. Per-list weights let a stronger
    retriever lead the ranking without the noisier retriever dragging
    the order around (standard pattern in hybrid retrieval literature).
    Deduplication is by (source, chunk_index) so a near-duplicate chunk
    appearing in two lists still counts once per list rather than
    double-counting.
    """
    if weights is None:
        weights = [1.0] * len(ranked_lists)
    if len(weights) != len(ranked_lists):
        raise ValueError("weights length must match ranked_lists length")

    scores: dict[tuple, float] = {}
    docs_by_key: dict[tuple, Document] = {}

    for weight, ranked in zip(weights, ranked_lists):
        for rank, doc in enumerate(ranked):
            key = (doc.metadata.get("source"), doc.metadata.get("chunk_index"))
            if key not in docs_by_key:
                docs_by_key[key] = doc
                scores[key] = 0.0
            scores[key] += weight / (k + rank + 1)

    # Sort by fused score desc, return the underlying Documents in order.
    return [docs_by_key[key] for key, _ in sorted(scores.items(), key=lambda kv: kv[1], reverse=True)]


def _should_use_hybrid(query: str) -> bool:
    """
    Cheap pre-check: should this query pay the BM25 cost?
    Returns False for queries that are already well-served by vector
    similarity alone (exact file paths, very short identifier lookups),
    True for everything else. Heuristic, not a learned model -- the
    eval harness measures whether it's right, and a few real misses
    are cheaper to retune than a router model would be.
    """
    if _FILE_PATH_RE.search(query):
        return False
    tokens = _BM25_TOKEN_RE.findall(query)
    return len(tokens) > _MAX_VECTOR_ONLY_TOKENS


async def hybrid_search(query: str, k: int = 5, doc_type: str | None = None, repo_id: str | None = None) -> list[Document]:
    """
    Hybrid BM25 + vector retrieval, fused via reciprocal rank fusion.
    Routes trivially-routable queries to vector-only to save the BM25
    cost; otherwise runs both retrievers and fuses. doc_type is honored
    on the vector side; BM25 currently has no doc_type filter (would
    need to be threaded through the cached index). No LLM-based query
    expansion here -- measure plain BM25 + vector first, decide whether
    the expansion's quality bump is worth its latency/cost on top.
    """
    if not _should_use_hybrid(query):
        # Vector-only fast path. Sync, but kept inside an async fn so
        # the tool signature stays uniform with multi_search.
        return search(query, k=k, doc_type=doc_type, repo_id=repo_id)

    vector_results = search(query, k=k, doc_type=doc_type, repo_id=repo_id)

    if not repo_id:
        # BM25 is repo-scoped (its index is per-repo). Without a repo_id
        # there's no keyword index to query, so hybrid collapses to
        # vector-only rather than silently mixing chunks from unrelated
        # repos into the result.
        return vector_results

    # BM25 over the repo's full chunk set. Fetch top 2*k to give fusion
    # candidates beyond the immediate vector hits -- pure BM25 often
    # surfaces a chunk the vector retriever ranked low.
    index, docs = _build_bm25_index(repo_id)
    query_tokens = _BM25_TOKEN_RE.findall(query.lower())
    scores = index.get_scores(query_tokens)
    ranked_indices = scores.argsort()[::-1][: 2 * k]
    bm25_results = [docs[i] for i in ranked_indices if scores[i] > 0]

    fused = _reciprocal_rank_fusion(
        [vector_results, bm25_results],
        weights=[VECTOR_WEIGHT, BM25_WEIGHT],
    )
    return fused[:k]
