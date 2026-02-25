from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "dev"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    log_level: str = "INFO"

    database_url: str = "postgresql+asyncpg://mentorix:mentorix@localhost:5432/mentorix"
    redis_url: str = "redis://localhost:6379/0"
    mongodb_url: str = "mongodb://localhost:27017"
    mongodb_db_name: str = "mentorix"
    memory_store_backend: str = "mongo"
    memory_dual_write: bool = False
    mongodb_snapshots_ttl_days: int = 0
    mongodb_episodes_ttl_days: int = 0
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
    grounding_workspace_root: str = ""  # If set (e.g. /workspace in Docker), base path for grounding_data_dir
    grounding_data_dir: str = "class-10-maths"
    grounding_syllabus_relative_path: str = "syllabus/syllabus.pdf"
    grounding_chapters_dir: str = "chapters"
    grounding_chapter_count: int = 5
    grounding_chunk_size: int = 900
    grounding_chunk_overlap: int = 120
    grounding_prepare_on_start: bool = False
    grounding_require_ready: bool = False
    gateway_auth_enabled: bool = False
    gateway_api_key: str = ""

    max_state_transitions: int = 10
    max_adaptation_shifts_per_concept: int = 2
    runtime_data_dir: str = "data/system"
    scheduler_enabled: bool = False
    scheduler_tick_seconds: int = 2
    role_model_governance_enabled: bool = True
    enforce_local_verifier: bool = False
    model_registry_file: str = "CONFIG/models_registry.json"
    reasoning_score_threshold: int = 85
    reasoning_max_refinements: int = 1

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
