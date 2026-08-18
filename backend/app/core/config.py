from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):

    embedding_provider: str = "local"
    embedding_model_local: str = "sentence-transformers/all-MiniLM-L6-v2"
    
    llm_provider: str = "gemini"  # "groq" or "gemini"

    google_api_key: str | None = None
    google_model_name: str = "gemini-2.5-flash-lite"
    
    groq_api_key: str | None = None
    groq_model_name: str = "llama-3.3-70b-versatile"

    chroma_host: str = "chroma"
    chroma_port: int = 8000
    clone_dir: str = "./cloned_repos"

    jwt_secret_key: str = "dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60
    
    jwt_refresh_secret_key: str = "dev-refresh-secret-change-me"
    jwt_refresh_expire_minutes: int = 60 * 24 * 7   # 7 days
    demo_username: str = "admin"
    demo_password_hash: str = ""

    redis_url: str = "redis://localhost:6379/0"
    database_url: str = "sqlite:///./reposage.db"

    rate_limit_chat_per_day: int = 50
    rate_limit_ingest_per_day: int = 10

    # Auth cookies. Set `cookie_secure=true` in prod (or via env
    # COOKIE_SECURE=true) -- browsers refuse to set Secure cookies on
    # plain HTTP, so the default is False for dev. SameSite=Lax is the
    # entire CSRF defense (browsers don't send Lax cookies on cross-
    # origin POST/PUT/DELETE) -- no separate CSRF token needed.
    cookie_secure: bool = False
    cookie_samesite: str = "lax"
    cookie_domain: str | None = None      # None = host-only (right default)
    cookie_path: str = "/"

    # CORS — explicit origins required because allow_credentials=True
    # forbids "*". In dev: Vite proxy on 5173 + raw backend on 8000.
    # In prod the frontend and backend are same-origin, so CORS rarely
    # matters, but the list still has to be sane for direct probes.
    cors_allowed_origins: list[str] = [
        "http://localhost:5173",
        "http://localhost:8000",
    ]

    gh_client_id: str | None = None
    gh_client_secret: str | None = None

    gh_redirect_uri: str = "http://127.0.0.1:8000/auth/github/callback"
    frontend_base_url: str = "http://localhost"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )

settings = Settings()
