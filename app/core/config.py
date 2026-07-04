from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    embedding_provider: str = "local"   # "local" or "openai"
    embedding_model_local: str = "sentence-transformers/all-MiniLM-L6-v2"
    openai_api_key: str | None = None
    chroma_persist_dir: str = "./chroma_db"
    clone_dir: str = "./cloned_repos"

    class Config:
        env_file = ".env"

settings = Settings()
