"""Helpers for authenticated repository access."""

from __future__ import annotations

from urllib.parse import quote, urlsplit, urlunsplit

from ..db.models import Project

PROJECT_ACCESS_TOKEN_KEY = "repo_access_token"


def project_access_token(project: Project) -> str | None:
    value = (project.config or {}).get(PROJECT_ACCESS_TOKEN_KEY)
    if not isinstance(value, str):
        return None
    token = value.strip()
    return token or None


def canonical_repo_url(repo_url: str) -> str:
    """Normalize known SCM URL variants to avoid auth-breaking redirects."""
    candidate = (repo_url or "").strip()
    parsed = urlsplit(candidate)
    if parsed.scheme != "https" or not parsed.netloc:
        return candidate
    if parsed.hostname != "www.github.com":
        return candidate

    auth = ""
    if parsed.username:
        auth = quote(parsed.username, safe="")
        if parsed.password:
            auth += ":" + quote(parsed.password, safe="")
        auth += "@"
    host = "github.com"
    if parsed.port:
        host = f"{host}:{parsed.port}"
    return urlunsplit((parsed.scheme, f"{auth}{host}", parsed.path, parsed.query, parsed.fragment))


def repo_url_with_token(repo_url: str, access_token: str | None) -> str:
    """Embed token in HTTPS URL for git clone/authenticated fetches."""
    repo_url = canonical_repo_url(repo_url)
    if not access_token:
        return repo_url

    parsed = urlsplit(repo_url)
    if parsed.scheme != "https" or not parsed.netloc:
        return repo_url
    if "@" in parsed.netloc:
        return repo_url

    netloc = f"x-access-token:{quote(access_token, safe='')}@{parsed.netloc}"
    return urlunsplit((parsed.scheme, netloc, parsed.path, parsed.query, parsed.fragment))


def redact_access_token(text: str, access_token: str | None) -> str:
    if not access_token:
        return text
    return text.replace(access_token, "***")
