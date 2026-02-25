import logging
import re
import sys
# Domain names for structured logging (onboarding, planning, adaptation, scheduling, compliance, RAG).
DOMAIN_ONBOARDING = "onboarding"
DOMAIN_PLANNING = "planning"
DOMAIN_ADAPTATION = "adaptation"
DOMAIN_SCHEDULING = "scheduling"
DOMAIN_COMPLIANCE = "compliance"
DOMAIN_RAG = "rag"


def get_domain_logger(name: str, domain: str) -> logging.LoggerAdapter[logging.Logger]:
    """Return a logger that adds the given domain to every log record (for filtering by domain)."""
    base = logging.getLogger(name)
    return logging.LoggerAdapter(base, {"domain": domain})


class DomainDefaultFilter(logging.Filter):
    """Ensure record has a 'domain' attribute so format string %(domain)s never fails."""

    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "domain"):
            record.domain = "app"  # type: ignore[attr-defined]
        return True


_SECRET_PATTERNS = [
    re.compile(r"(?i)(x-goog-api-key\s*[=:]\s*)([^\s,;]+)"),
    re.compile(r"(?i)(api[_-]?key\s*[=:]\s*)([^\s,;]+)"),
    re.compile(r"(?i)(authorization\s*[=:]\s*bearer\s+)([^\s,;]+)"),
    re.compile(r"(?i)(token\s*[=:]\s*)([^\s,;]+)"),
    re.compile(r"(?i)(password\s*[=:]\s*)([^\s,;]+)"),
]


def redact_secrets(message: str) -> str:
    text = str(message or "")
    for pattern in _SECRET_PATTERNS:
        text = pattern.sub(r"\1[REDACTED]", text)
    return text


class SecretRedactionFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact_secrets(record.getMessage())
        record.args = ()
        return True


class SuppressHealthCheckFilter(logging.Filter):
    """Drop uvicorn access log lines for GET /health to reduce noise from Docker healthchecks."""

    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage() if hasattr(record, "getMessage") else str(record.msg)
        if "/health" in msg and "200" in msg:
            return False
        return True


def configure_logging(level: str = "INFO") -> None:
    redaction_filter = SecretRedactionFilter()
    domain_filter = DomainDefaultFilter()
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)s | [%(domain)s] | %(name)s | %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )
    root = logging.getLogger()
    for handler in root.handlers:
        handler.addFilter(domain_filter)
        handler.addFilter(redaction_filter)
    # Avoid verbose request URL logging from http clients.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    # Suppress access log for GET /health (Docker healthcheck) to reduce console noise.
    uv_access = logging.getLogger("uvicorn.access")
    uv_access.addFilter(SuppressHealthCheckFilter())