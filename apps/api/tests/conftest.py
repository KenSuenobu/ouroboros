"""Shared pytest fixtures."""

from __future__ import annotations

import asyncio
import os
import tempfile
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest
import pytest_asyncio


@pytest.fixture(scope="session")
def event_loop() -> Iterator[asyncio.AbstractEventLoop]:
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def tmp_repo() -> Iterator[Path]:
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        (root / "README.md").write_text("hello\n", encoding="utf-8")
        (root / "src").mkdir()
        (root / "src" / "app.py").write_text("print('ok')\n", encoding="utf-8")
        yield root


@pytest_asyncio.fixture
async def isolated_db(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> AsyncIterator[None]:
    """Force the API to use a fresh sqlite DB inside tmp_path."""
    db_path = tmp_path / "test.sqlite"
    os.environ["OUROBOROS_DB_URL"] = f"sqlite+aiosqlite:///{db_path}"
    os.environ["OUROBOROS_DATA_DIR"] = str(tmp_path)
    from ouroboros_api.db import session as session_module

    session_module._engine = None  # type: ignore[attr-defined]
    yield
