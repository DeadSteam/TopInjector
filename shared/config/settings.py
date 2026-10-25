"""Application settings loaded from environment variables."""

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Placeholder secret shipped in the repo. Usable only in debug; refused once debug is off.
DEFAULT_JWT_SECRET = "change-me-in-production-at-least-32-chars"


class Settings(BaseSettings):
    """Shared settings for the modular monolith."""

    # extra="ignore": a deployment .env may carry keys for other services (e.g. RABBITMQ_PASSWORD)
    # that this model doesn't map; ignore them instead of refusing to start.
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", populate_by_name=True, extra="ignore"
    )

    # Database
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_user: str = "ghostlab"
    postgres_password: str = "ghostlab_pass"
    postgres_db: str = "ghostlab"
    # Full DSN; when set it wins over the postgres_* components.
    database_url_override: str | None = Field(default=None, alias="DATABASE_URL")

    @property
    def database_url(self) -> str:
        if self.database_url_override:
            return self.database_url_override
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    # Redis
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: str = ""

    @property
    def redis_auth(self) -> str:
        """``:password@`` prefix for Redis URLs, or empty when no password is set."""
        return f":{self.redis_password}@" if self.redis_password else ""

    @property
    def redis_url(self) -> str:
        return f"redis://{self.redis_auth}{self.redis_host}:{self.redis_port}/{self.redis_db}"

    # RabbitMQ
    rabbitmq_url: str = "amqp://guest:guest@localhost:5672"

    # Auth
    jwt_secret: str = DEFAULT_JWT_SECRET
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 30
    refresh_token_days: int = 7
    # Comma-separated emails allowed to see /api/projects/admin/stats; empty = nobody
    admin_emails: str = ""
    # Timezone of projects' scheduling windows ("07:00"–"22:00") and of "today" for daily quotas
    schedule_timezone: str = "Europe/Moscow"

    @property
    def admin_email_set(self) -> set[str]:
        return {e.strip().lower() for e in self.admin_emails.split(",") if e.strip()}

    # Server
    debug: bool = True
    host: str = "0.0.0.0"
    port: int = 8000
    allowed_origins: list[str] = ["http://localhost:5173", "http://localhost:4173"]
    frontend_url: str = "http://localhost:5173"
    # Set True in production so auth cookies carry the Secure flag (HTTPS only).
    cookie_secure: bool = False

    # Logging
    log_level: str = "INFO"

    # Email (SMTP)
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    email_enabled: bool = False

    @model_validator(mode="after")
    def _reject_insecure_secret(self) -> "Settings":
        """Once debug is off, the signing secret must be set and long enough to resist guessing."""
        if not self.debug and (self.jwt_secret == DEFAULT_JWT_SECRET or len(self.jwt_secret) < 32):
            raise ValueError(
                "JWT_SECRET must be set to a unique value of at least 32 characters when DEBUG is off"
            )
        return self


settings = Settings()
