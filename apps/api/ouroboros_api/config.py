"""Settings loaded from env + .env. Local-first defaults; multi-tenant-ready."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _default_data_dir() -> Path:
    return Path("./data")


def _sqlite_db_url_for_data_dir(data_dir: Path) -> str:
    sqlite_path = data_dir / "ouroboros.sqlite"
    if sqlite_path.is_absolute():
        return f"sqlite+aiosqlite:///{sqlite_path.as_posix()}"
    return f"sqlite+aiosqlite:///./{sqlite_path.as_posix().lstrip('./')}"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="OUROBOROS_", env_file=".env", extra="ignore")

    db_url: str = Field(default="")
    data_dir: Path = Field(default_factory=_default_data_dir)

    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])

    bind_host: str = "127.0.0.1"
    bind_port: int = 8000

    default_workspace_slug: str = "default"

    secrets_backend: str = "keyring"
    secrets_keyring_service: str = "ouroboros"

    mcp_registry_url: str = "https://registry.modelcontextprotocol.io"
    mcp_registry_cache_ttl_seconds: int = 3600

    log_level: str = "INFO"

    def db_url_resolved(self) -> str:
        if self.db_url:
            return self.db_url
        return _sqlite_db_url_for_data_dir(self.data_dir)

    def runs_dir(self) -> Path:
        return self.data_dir / "runs"

    def ensure_dirs(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.runs_dir().mkdir(parents=True, exist_ok=True)


settings = Settings()
settings.ensure_dirs()
