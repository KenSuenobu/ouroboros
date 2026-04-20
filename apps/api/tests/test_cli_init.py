from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from ouroboros_api.cli import cli


def test_init_writes_env_and_example() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(cli, ["init"], input="\n\n")

        assert result.exit_code == 0
        env_path = Path(".env")
        env_example_path = Path(".env.example")
        assert env_path.exists()
        assert env_example_path.exists()

        env_contents = env_path.read_text(encoding="utf-8")
        assert "OUROBOROS_DATA_DIR=./data" in env_contents
        assert "OUROBOROS_DB_URL=sqlite+aiosqlite:///./data/ouroboros.sqlite" in env_contents
        assert env_contents == env_example_path.read_text(encoding="utf-8")


def test_init_does_not_overwrite_existing_env() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        Path(".env").write_text("OUROBOROS_DATA_DIR=/tmp/keep-me\n", encoding="utf-8")

        result = runner.invoke(cli, ["init"], input="\n\n")

        assert result.exit_code == 0
        assert ".env exists; not overwriting" in result.output
        assert Path(".env").read_text(encoding="utf-8") == "OUROBOROS_DATA_DIR=/tmp/keep-me\n"
        assert not Path(".env.example").exists()
