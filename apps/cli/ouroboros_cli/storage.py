"""Token storage backed by the OS keyring with a JSON fallback."""

from __future__ import annotations

import json
import os
import stat
from pathlib import Path

SERVICE = "ouroboros-cli"

try:
    import keyring as _keyring
    import keyring.errors as _keyring_errors

    _HAVE_KEYRING = True
except Exception:  # pragma: no cover - optional dep
    _keyring = None
    _keyring_errors = None  # type: ignore[assignment]
    _HAVE_KEYRING = False


def _config_dir() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    path = Path(base) / "ouroboros"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _config_file() -> Path:
    return _config_dir() / "cli.json"


def _read_config() -> dict[str, str]:
    path = _config_file()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except Exception:
        return {}


def _write_config(data: dict[str, str]) -> None:
    path = _config_file()
    path.write_text(json.dumps(data, indent=2))
    try:
        path.chmod(stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        pass


def get_token(api_url: str) -> str | None:
    if _HAVE_KEYRING and _keyring is not None:
        try:
            value = _keyring.get_password(SERVICE, api_url)
            if value:
                return value
        except Exception:
            pass
    return _read_config().get(api_url)


def set_token(api_url: str, token: str) -> None:
    saved = False
    if _HAVE_KEYRING and _keyring is not None:
        try:
            _keyring.set_password(SERVICE, api_url, token)
            saved = True
        except Exception:
            saved = False
    if not saved:
        data = _read_config()
        data[api_url] = token
        _write_config(data)


def clear_token(api_url: str) -> None:
    if _HAVE_KEYRING and _keyring is not None:
        try:
            _keyring.delete_password(SERVICE, api_url)
        except Exception:
            pass
    data = _read_config()
    if api_url in data:
        del data[api_url]
        _write_config(data)
