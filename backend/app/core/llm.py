from app.core.config import settings

_model = None


def get_chat_model():
    global _model
    if _model is not None:
        return _model

    if settings.llm_provider == "groq":
        from langchain_groq import ChatGroq
        _model = ChatGroq(model=settings.groq_model_name, api_key=settings.groq_api_key)
    else:
        from langchain_google_genai import ChatGoogleGenerativeAI
        _model = ChatGoogleGenerativeAI(model=settings.google_model_name, api_key=settings.google_api_key)

    return _model
