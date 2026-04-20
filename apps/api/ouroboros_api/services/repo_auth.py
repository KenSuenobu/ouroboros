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


def repo_url_with_token(repo_url: str, access_token: str | None) -> str:
    """Embed token in HTTPS URL for git clone/authenticated fetches."""
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
