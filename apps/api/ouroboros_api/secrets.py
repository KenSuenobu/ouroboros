"""Pluggable secret backend. Defaults to the OS keyring; falls back to file-based storage."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol

from .config import settings


class SecretsBackend(Protocol):
    def get(self, ref: str) -> str | None: ...
    def set(self, ref: str, value: str) -> None: ...
    def delete(self, ref: str) -> None: ...


class KeyringBackend:
    """Wraps the OS keyring (best for desktop/local mode)."""

    def __init__(self, service: str) -> None:
        self.service = service

    def get(self, ref: str) -> str | None:
        try:
            import keyring

            return keyring.get_password(self.service, ref)
        except Exception:
            return None

    def set(self, ref: str, value: str) -> None:
        import keyring

        keyring.set_password(self.service, ref, value)

    def delete(self, ref: str) -> None:
        try:
            import keyring

            keyring.delete_password(self.service, ref)
        except Exception:
            pass


class FileBackend:
    """JSON-file fallback for headless / containerized installs."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _load(self) -> dict[str, str]:
        if not self.path.exists():
            return {}
        try:
            return json.loads(self.path.read_text("utf-8"))
        except Exception:
            return {}

    def _save(self, data: dict[str, str]) -> None:
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
        tmp.replace(self.path)

    def get(self, ref: str) -> str | None:
        return self._load().get(ref)

    def set(self, ref: str, value: str) -> None:
        data = self._load()
        data[ref] = value
        self._save(data)

    def delete(self, ref: str) -> None:
        data = self._load()
        data.pop(ref, None)
        self._save(data)


def _build() -> SecretsBackend:
    if settings.secrets_backend == "file":
        return FileBackend(settings.data_dir / "secrets" / "secrets.json")
    try:
        import keyring  # noqa: F401

        return KeyringBackend(settings.secrets_keyring_service)
    except Exception:
        return FileBackend(settings.data_dir / "secrets" / "secrets.json")


secrets: SecretsBackend = _build()
