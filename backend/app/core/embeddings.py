from app.core.config import settings


def get_embedding_function():
    """
    Returns a LangChain-compatible embedding function based on
    settings.embedding_provider. Keeping this as a single switch point
    means the rest of the app (ingestion, agent tools) never needs to
    know which backend is active.
    """
    if settings.embedding_provider == "openai":
        from langchain_openai import OpenAIEmbeddings
        return OpenAIEmbeddings(api_key=settings.openai_api_key)

    # default: local, free, no API key required
    from langchain_huggingface import HuggingFaceEmbeddings
    return HuggingFaceEmbeddings(model_name=settings.embedding_model_local)
