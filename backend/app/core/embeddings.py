from app.core.config import settings

_embedding_function = None


def get_embedding_function():
    """
    Cached at module level -- loading sentence-transformers weights is
    expensive (real disk I/O + model init), not something to repeat on
    every search_codebase call. Each process (api, worker) gets its own
    singleton, since it's an in-process ML model, not a shared service --
    that's a different concern from Chroma, which we already made a
    shared service specifically for the data itself.
    """
    global _embedding_function
    if _embedding_function is not None:
        return _embedding_function

    if settings.embedding_provider == "openai":
        from langchain_openai import OpenAIEmbeddings
        _embedding_function = OpenAIEmbeddings(api_key=settings.openai_api_key)
    else:
        from langchain_huggingface import HuggingFaceEmbeddings
        _embedding_function = HuggingFaceEmbeddings(model_name=settings.embedding_model_local)

    return _embedding_function
