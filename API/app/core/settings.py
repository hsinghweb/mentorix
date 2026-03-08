from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Central configuration for the Mentorix API.

    All settings can be overridden via environment variables (case-insensitive).
    Loaded from ``.env`` and ``CONFIG/local.env`` in order.
    """

    # ── Application ──────────────────────────────────────────────────
    app_env: str = Field("dev", description="Environment: dev | staging | production")
    app_host: str = Field("0.0.0.0", description="Host to bind the API server to")
    app_port: int = Field(8000, description="Port to bind the API server to")
    log_level: str = Field("INFO", description="Logging level: DEBUG | INFO | WARNING | ERROR")

    # ── Databases ────────────────────────────────────────────────────
    database_url: str = Field(
        "postgresql+asyncpg://mentorix:mentorix@localhost:5432/mentorix",
        description="PostgreSQL connection string (async). Stores learner profiles, tasks, assessments.",
    )
    redis_url: str = Field("redis://localhost:6379/0", description="Redis connection for caching and idempotency")
    mongodb_url: str = Field("mongodb://localhost:27017", description="MongoDB for content caching and memory store")
    mongodb_db_name: str = Field("mentorix", description="MongoDB database name")
    memory_store_backend: str = Field("mongo", description="Memory store backend: mongo | redis")
    memory_dual_write: bool = Field(False, description="If True, write to both memory stores for migration")
    mongodb_snapshots_ttl_days: int = Field(0, description="TTL for MongoDB profile snapshots (0 = no expiry)")
    mongodb_episodes_ttl_days: int = Field(0, description="TTL for MongoDB episode records (0 = no expiry)")
    session_ttl_seconds: int = Field(3600, description="Session TTL in seconds for in-memory caches")
    retention_cleanup_enabled: bool = Field(True, description="Enable periodic cleanup of old session/assessment data")
    session_retention_days: int = Field(30, description="Days to retain session logs and assessment results")

    # ── LLM Provider ─────────────────────────────────────────────────
    llm_provider: str = Field("gemini", description="LLM provider: gemini | ollama")
    llm_model: str = Field("gemini-2.5-flash", description="Default LLM model name")
    gemini_api_key: str = Field("", description="Google Gemini API key (required if llm_provider=gemini)")
    gemini_api_url: str = Field("", description="Custom Gemini API endpoint URL (optional)")
    ollama_base_url: str = Field("http://localhost:11434", description="Ollama server base URL")
    ollama_model: str = Field("qwen2.5:3b", description="Ollama model name for local inference")

    # ── Embeddings & Retrieval ───────────────────────────────────────
    embedding_provider: str = Field("ollama", description="Embedding provider: ollama | gemini")
    embedding_model: str = Field("nomic-embed-text", description="Embedding model name")
    embedding_dimensions: int = Field(768, description="Embedding vector dimensions")
    vector_backend: str = Field("pgvector", description="Vector storage backend: pgvector")
    include_generated_artifacts_in_retrieval: bool = Field(True, description="Include LLM-generated content in RAG retrieval")
    generated_artifacts_top_k: int = Field(2, description="Number of generated artifact chunks to include in retrieval")
    web_search_provider: str = Field("duckduckgo", description="Web search provider for fallback grounding")

    # ── Grounding / NCERT Data ───────────────────────────────────────
    grounding_workspace_root: str = Field("", description="Absolute base path for grounding data (e.g. /workspace)")
    grounding_data_dir: str = Field("class-10-maths", description="Directory containing NCERT chapter PDFs")
    grounding_syllabus_relative_path: str = Field("syllabus/syllabus.pdf", description="Path to syllabus PDF relative to grounding_data_dir")
    grounding_chapters_dir: str = Field("chapters", description="Subdirectory containing individual chapter PDFs")
    grounding_chapter_count: int = Field(5, description="Number of chapters to ingest at startup")
    grounding_chunk_size: int = Field(900, description="Character count per embedding chunk")
    grounding_chunk_overlap: int = Field(120, description="Overlap between adjacent chunks in characters")
    grounding_prepare_on_start: bool = Field(False, description="Auto-ingest grounding data on startup")
    grounding_require_ready: bool = Field(False, description="Block startup until grounding index is ready")

    # ── Authentication & Security ────────────────────────────────────
    gateway_auth_enabled: bool = Field(False, description="Enable API gateway auth (for external deployments)")
    gateway_api_key: str = Field("", description="API key for gateway authentication")
    jwt_secret: str = Field("mentorix-dev-secret-change-in-production", description="JWT signing secret — MUST change in production")
    jwt_algorithm: str = Field("HS256", description="JWT signing algorithm")
    jwt_expire_minutes: int = Field(60 * 24 * 7, description="JWT token expiry in minutes (default: 7 days)")
    admin_username: str = Field("admin", description="Admin dashboard login username")
    admin_password: str = Field("admin", description="Admin dashboard login password — MUST change in production")

    # ── Agent & Runtime ──────────────────────────────────────────────
    max_state_transitions: int = Field(10, description="Max state machine transitions per agent run")
    max_adaptation_shifts_per_concept: int = Field(2, description="Max difficulty adaptation shifts per concept per session")
    runtime_data_dir: str = Field("data/system", description="Directory for runtime data files")
    scheduler_enabled: bool = Field(False, description="Enable background scheduler (reminders, cleanup)")
    scheduler_tick_seconds: int = Field(2, description="Scheduler polling interval in seconds")
    role_model_governance_enabled: bool = Field(True, description="Enable model governance validation on startup")
    enforce_local_verifier: bool = Field(False, description="Require local verification pass before LLM output acceptance")
    model_registry_file: str = Field("CONFIG/models_registry.json", description="Path to LLM model registry JSON file")

    # ── Content Generation ───────────────────────────────────────────
    reasoning_score_threshold: int = Field(85, description="Minimum reasoning quality score (0-100) for content acceptance")
    reasoning_max_refinements: int = Field(1, description="Max LLM re-generation attempts if content fails quality check")
    math_format_fix_second_pass_enabled: bool = Field(False, description="Enable LLM second-pass to fix unresolved math formatting")
    reading_min_seconds: int = Field(60, description="Minimum reading time requirement in seconds")
    reading_max_seconds: int = Field(300, description="Maximum reading time cap in seconds")
    reading_estimate_wpm: int = Field(150, description="Words-per-minute for reading time estimation")

    # ── Email & Reminders ────────────────────────────────────────────
    email_host: str = Field("", description="SMTP host for email delivery (e.g. smtp.gmail.com)")
    email_port: int = Field(587, description="SMTP port (587 for TLS, 465 for SSL)")
    email_user: str = Field("", description="SMTP username / email address")
    email_pass: str = Field("", description="SMTP password or app-specific password — use secrets management in production")
    email_from: str = Field("", description="Sender email address for outbound emails")
    gmail_api_credentials_json: str = Field("", description="Path to Gmail API OAuth credentials JSON (alternative to SMTP)")
    reminder_dispatch_enabled: bool = Field(False, description="Enable automated reminder email dispatch")
    reminder_scan_interval_seconds: int = Field(86400, description="Interval between reminder eligibility scans (seconds)")
    reminder_rate_limit_hours: int = Field(24, description="Minimum hours between reminder emails to same learner")
    reminder_dispatch_max_attempts: int = Field(2, description="Max retry attempts per reminder dispatch")
    reminder_dispatch_retry_backoff_seconds: int = Field(2, description="Backoff between reminder dispatch retries")
    reminder_dispatch_global_cooldown_seconds: int = Field(60, description="Global cooldown between consecutive reminder dispatches")

    model_config = SettingsConfigDict(
        env_file=(".env", "CONFIG/local.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
