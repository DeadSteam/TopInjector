"""Application settings loaded from environment variables."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Shared settings for the modular monolith."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", populate_by_name=True)

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

    @property
    def redis_url(self) -> str:
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"

    # RabbitMQ
    rabbitmq_url: str = "amqp://guest:guest@localhost:5672"

    # Auth
    jwt_secret: str = "change-me-in-production-at-least-32-chars"
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 30
    refresh_token_days: int = 7

    # Server
    debug: bool = True
    host: str = "0.0.0.0"
    port: int = 8000
    allowed_origins: list[str] = ["http://localhost:5173", "http://localhost:4173"]

    # Logging
    log_level: str = "INFO"


settings = Settings()
