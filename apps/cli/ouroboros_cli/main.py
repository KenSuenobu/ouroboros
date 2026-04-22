"""`ouroboros` command-line entry point."""

from __future__ import annotations

import getpass
import os
import sys
import webbrowser
from typing import Annotated, Optional

import httpx
import typer
from rich.console import Console
from rich.table import Table

from . import __version__
from .storage import clear_token, get_token, set_token

DEFAULT_API_URL = "http://localhost:8000"

app = typer.Typer(
    add_completion=False,
    help="Ouroboros command-line client.",
    no_args_is_help=True,
)
console = Console()


def _resolve_api(api: Optional[str]) -> str:
    return (api or os.environ.get("OUROBOROS_API_URL") or DEFAULT_API_URL).rstrip("/")


def _client(api_url: str, token: Optional[str] = None) -> httpx.Client:
    headers: dict[str, str] = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return httpx.Client(base_url=api_url, headers=headers, timeout=30.0)


def _error(message: str) -> None:
    console.print(f"[bold red]error:[/] {message}")
    raise typer.Exit(code=1)


@app.callback()
def main(
    version: Annotated[
        bool,
        typer.Option("--version", help="Show version and exit.", is_eager=True),
    ] = False,
) -> None:
    if version:
        console.print(f"ouroboros {__version__}")
        raise typer.Exit()


@app.command()
def login(
    email: Annotated[Optional[str], typer.Option(help="Email address.")] = None,
    github: Annotated[bool, typer.Option("--github", help="Sign in with GitHub OAuth.")] = False,
    api: Annotated[Optional[str], typer.Option(help="API base URL.")] = None,
) -> None:
    """Authenticate against an Ouroboros API and store the session token locally."""
    api_url = _resolve_api(api)

    if github:
        _login_github(api_url)
        return

    if not email:
        email = typer.prompt("Email")
    password = getpass.getpass("Password: ")
    if not password:
        _error("password is required")

    with _client(api_url) as client:
        try:
            res = client.post(
                "/api/auth/login", json={"email": email, "password": password}
            )
        except httpx.HTTPError as exc:
            _error(f"failed to reach {api_url}: {exc}")
            return  # unreachable, mypy

    if res.status_code != 200:
        try:
            detail = res.json().get("detail")
        except Exception:
            detail = res.text or res.reason_phrase
        _error(f"login failed: {detail}")

    cookie = res.cookies.get("ob_session")
    if not cookie:
        _error("server did not return a session cookie; aborting.")
        return  # unreachable
    set_token(api_url, cookie)
    user = res.json()
    console.print(
        f"[green]signed in[/] as [bold]{user.get('email')}[/] on {api_url}"
    )


def _login_github(api_url: str) -> None:
    """Browser-assisted GitHub login.

    Opens the API's `/api/auth/oauth/github/start` endpoint in the user's
    browser. The browser completes OAuth and lands the user inside the web
    UI with a fresh `ob_session` cookie. The user then pastes that cookie
    here so the CLI can use it as an API token. We avoid spinning up a
    local HTTP server so this works inside SSH sessions and remote shells.
    """
    url = f"{api_url}/api/auth/oauth/github/start"
    console.print(
        "Opening your browser to authorize via GitHub.\n"
        f"If it doesn't open, visit:\n  {url}\n\n"
        "After signing in, copy the value of the [bold]ob_session[/] cookie\n"
        "(DevTools → Application → Cookies) and paste it below."
    )
    try:
        webbrowser.open(url)
    except Exception:
        pass
    token = getpass.getpass("Paste ob_session cookie: ").strip()
    if not token:
        _error("no token provided")

    with _client(api_url, token) as client:
        res = client.get("/api/auth/me")
    if res.status_code != 200:
        _error("token rejected by API; please try again")
    set_token(api_url, token)
    user = res.json()
    console.print(
        f"[green]signed in[/] as [bold]{user.get('email')}[/] on {api_url}"
    )


@app.command()
def logout(
    api: Annotated[Optional[str], typer.Option(help="API base URL.")] = None,
) -> None:
    """Revoke the local session and remove the token from the keyring."""
    api_url = _resolve_api(api)
    token = get_token(api_url)
    if not token:
        console.print("[yellow]no active session for[/] " + api_url)
        return

    with _client(api_url, token) as client:
        try:
            client.post("/api/auth/logout")
        except httpx.HTTPError:
            pass
    clear_token(api_url)
    console.print("[green]signed out[/]")


@app.command()
def whoami(
    api: Annotated[Optional[str], typer.Option(help="API base URL.")] = None,
) -> None:
    """Show the authenticated user and workspace memberships."""
    api_url = _resolve_api(api)
    token = get_token(api_url)
    if not token:
        _error(f"no token for {api_url}; run `ouroboros login` first.")

    with _client(api_url, token) as client:
        res = client.get("/api/auth/me")
    if res.status_code == 401:
        clear_token(api_url)
        _error("session expired; run `ouroboros login` again")
    if res.status_code != 200:
        _error(f"{res.status_code}: {res.text}")

    user = res.json()
    console.print(f"[bold]{user.get('display_name') or user.get('email')}[/] <{user.get('email')}>")
    console.print(f"  api:    {api_url}")
    console.print(f"  active: {'yes' if user.get('is_active') else 'no'}")
    console.print(f"  oauth:  {', '.join(user.get('linked_oauth') or []) or '-'}")

    table = Table(title="Workspaces", show_lines=False, padding=(0, 1))
    table.add_column("Slug")
    table.add_column("Name")
    table.add_column("Role")
    for m in user.get("memberships") or []:
        table.add_row(m.get("workspace_slug", ""), m.get("workspace_name", ""), m.get("role", ""))
    console.print(table)


def _entrypoint() -> None:  # pragma: no cover - thin wrapper for `python -m`
    try:
        app()
    except KeyboardInterrupt:
        sys.exit(130)


if __name__ == "__main__":  # pragma: no cover
    _entrypoint()
