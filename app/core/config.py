from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    embedding_provider: str = "local"
    embedding_model_local: str = "sentence-transformers/all-MiniLM-L6-v2"
    google_api_key: str | None = None
    chroma_persist_dir: str = "./chroma_db"
    clone_dir: str = "./cloned_repos"

    jwt_secret_key: str = "dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60
    demo_username: str = "admin"
    demo_password_hash: str = ""

    redis_url: str = "redis://localhost:6379/0"
    database_url: str = "sqlite:///./reposage.db"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )

settings = Settings()