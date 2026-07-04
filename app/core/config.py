from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    embedding_provider: str = "local"
    embedding_model_local: str = "sentence-transformers/all-MiniLM-L6-v2"
    openai_api_key: str | None = None
    chroma_persist_dir: str = "./chroma_db"
    clone_dir: str = "./cloned_repos"

    # auth
    jwt_secret_key: str = "dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60
    demo_username: str = "admin"
    demo_password_hash: str = ""  # set via .env, generated below

    class Config:
        env_file = ".env"

settings = Settings()
