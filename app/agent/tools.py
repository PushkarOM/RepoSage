from langchain_core.tools import tool
from app.ingestion.vectorstore import search


@tool
def search_codebase(query: str, doc_type: str | None = None) -> str:
    """Search the ingested repository for code or documentation relevant
    to the query. Use this to find how something is implemented, where a
    feature lives, or what the docs say about a topic.

    Args:
        query: What to search for, e.g. "how does authentication work".
        doc_type: Optional filter, either "code" or "doc". Leave unset
            to search both.
    """
    results = search(query, k=5, doc_type=doc_type)

    if not results:
        return "No relevant results found in the ingested repository."

    formatted = []
    for r in results:
        source = r.metadata.get("source", "unknown")
        formatted.append(f"[{source}]\n{r.page_content}")

    return "\n\n---\n\n".join(formatted)
