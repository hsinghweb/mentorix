from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "dev"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    log_level: str = "INFO"

    database_url: str = "postgresql+asyncpg://mentorix:mentorix@localhost:5432/mentorix"
    redis_url: str = "redis://localhost:6379/0"
    session_ttl_seconds: int = 3600
    retention_cleanup_enabled: bool = True
    session_retention_days: int = 30

    llm_provider: str = "gemini"
    llm_model: str = "gemini-2.5-flash"
    gemini_api_key: str = ""
    gemini_api_url: str = ""
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:3b"

    embedding_provider: str = "ollama"
    embedding_model: str = "nomic-embed-text"
    embedding_dimensions: int = 768
    vector_backend: str = "pgvector"
    include_generated_artifacts_in_retrieval: bool = True
    generated_artifacts_top_k: int = 2
    web_search_provider: str = "duckduckgo"

    max_state_transitions: int = 10
    max_adaptation_shifts_per_concept: int = 2

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
