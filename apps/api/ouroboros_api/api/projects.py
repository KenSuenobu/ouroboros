"""Project CRUD."""

from __future__ import annotations

import anyio
import httpx
import os
import subprocess
from urllib.parse import urlsplit
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..db.models import Project, Workspace
from ..services.repo_auth import (
    PROJECT_ACCESS_TOKEN_KEY,
    canonical_repo_url,
    project_access_token,
    redact_access_token,
    repo_url_with_token,
)
from ..services.repo_introspect import introspect_project_commands, repo_introspector
from .deps import db_session, workspace
from .schemas import (
    GitHubDeviceOAuthPollIn,
    GitHubDeviceOAuthPollOut,
    GitHubDeviceOAuthStartIn,
    GitHubDeviceOAuthStartOut,
    ProjectIn,
    ProjectIntrospectionOut,
    ProjectOut,
    ProjectRepoTestIn,
    ProjectRepoTestOut,
)

router = APIRouter(prefix="/api/projects", tags=["projects"])


def _project_out(project: Project) -> ProjectOut:
    config = dict(project.config or {})
    has_access_token = bool(config.pop(PROJECT_ACCESS_TOKEN_KEY, ""))
    return ProjectOut(
        id=project.id,
        workspace_id=project.workspace_id,
        name=project.name,
        repo_url=project.repo_url,
        scm_kind=project.scm_kind,
        default_branch=project.default_branch,
        local_clone_hint=project.local_clone_hint,
        default_flow_id=project.default_flow_id,
        build_command=project.build_command,
        test_command=project.test_command,
        config=config,
        has_access_token=has_access_token,
        created_at=project.created_at,
        updated_at=project.updated_at,
    )


def _apply_access_token(project: Project, payload: ProjectIn) -> None:
    if "access_token" not in payload.model_fields_set:
        return
    config = dict(project.config or {})
    token = (payload.access_token or "").strip()
    if token:
        config[PROJECT_ACCESS_TOKEN_KEY] = token
    else:
        config.pop(PROJECT_ACCESS_TOKEN_KEY, None)
    project.config = config


def _is_github_repo_url(repo_url: str) -> bool:
    candidate = repo_url.strip()
    parsed = urlsplit(candidate)
    if parsed.scheme == "https" and parsed.hostname in {"github.com", "www.github.com"}:
        return True
    return candidate.lower().startswith("git@github.com:")


def _parse_github_owner_repo(repo_url: str) -> tuple[str, str] | None:
    candidate = canonical_repo_url(repo_url)
    parsed = urlsplit(candidate)
    if parsed.scheme == "https" and parsed.hostname == "github.com":
        parts = [p for p in parsed.path.split("/") if p]
        if len(parts) < 2:
            return None
        owner = parts[0]
        repo = parts[1][:-4] if parts[1].endswith(".git") else parts[1]
        return (owner, repo) if owner and repo else None
    if candidate.lower().startswith("git@github.com:"):
        path = candidate.split(":", 1)[1]
        parts = [p for p in path.split("/") if p]
        if len(parts) < 2:
            return None
        owner = parts[0]
        repo = parts[1][:-4] if parts[1].endswith(".git") else parts[1]
        return (owner, repo) if owner and repo else None
    return None


def _test_github_repo_access(
    owner: str, repo: str, default_branch: str, access_token: str | None
) -> tuple[bool, str]:
    base_headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "ouroboros-api/repo-check",
    }
    auth_headers = [None]
    if access_token:
        # GitHub supports bearer-style tokens, while some setups still expect "token".
        auth_headers = [f"Bearer {access_token}", f"token {access_token}"]

    def auth_error_message(response: httpx.Response) -> str:
        detail = ""
        try:
            payload = response.json()
            if isinstance(payload, dict):
                detail = str(payload.get("message") or "")
        except Exception:
            detail = ""
        granted = (response.headers.get("x-oauth-scopes") or "").strip()
        required = (response.headers.get("x-accepted-oauth-scopes") or "").strip()
        parts = [detail or "GitHub authentication failed."]
        if required:
            parts.append(f"required scopes: {required}")
        if granted:
            parts.append(f"granted scopes: {granted}")
        if not required and not granted:
            parts.append(
                "Ensure the token can access this repository "
                "(classic PAT: repo; fine-grained PAT: repository access + Contents: Read)."
            )
        return " ".join(parts)

    try:
        with httpx.Client(timeout=8.0, headers=base_headers, follow_redirects=True) as client:
            last_auth_message: str | None = None
            for auth_header in auth_headers:
                headers = dict(base_headers)
                if auth_header:
                    headers["Authorization"] = auth_header
                repo_res = client.get(f"https://api.github.com/repos/{owner}/{repo}", headers=headers)
                if repo_res.status_code in {401, 403}:
                    last_auth_message = auth_error_message(repo_res)
                    continue
                if repo_res.status_code == 200:
                    branch_res = client.get(
                        f"https://api.github.com/repos/{owner}/{repo}/branches/{default_branch}",
                        headers=headers,
                    )
                    if branch_res.status_code == 200:
                        return True, "Repository is reachable and branch is accessible."
                    if branch_res.status_code == 404:
                        return False, f"Repository is reachable, but branch {default_branch!r} was not found."
                    if branch_res.status_code in {401, 403}:
                        return False, auth_error_message(branch_res)
                    return False, f"Repository reachable, but branch check failed ({branch_res.status_code})."
                if repo_res.status_code == 404:
                    if access_token:
                        return (
                            False,
                            "Repository not found. If this is private, ensure the token has repository access "
                            "(classic PAT: repo; fine-grained PAT: repository access + Contents: Read).",
                        )
                    return (
                        False,
                        "Repository not publicly accessible. Add a repository access token for private repos.",
                    )
                return False, f"GitHub repository check failed ({repo_res.status_code})."
            if last_auth_message:
                return False, last_auth_message
            return False, "GitHub repository check failed."
    except httpx.TimeoutException:
        return False, "GitHub API check timed out."
    except Exception as exc:
        return False, f"GitHub repository check failed: {exc}"


def _test_repo_access_values(
    repo_url: str, default_branch: str, access_token: str | None
) -> tuple[bool, str]:
    github = _parse_github_owner_repo(repo_url)
    if github:
        return _test_github_repo_access(github[0], github[1], default_branch, access_token)

    repo_url = repo_url_with_token(repo_url, access_token)
    try:
        subprocess.run(
            ["git", "ls-remote", "--heads", repo_url, default_branch],
            check=True,
            capture_output=True,
            timeout=20,
            env={
                **os.environ,
                "GIT_TERMINAL_PROMPT": "0",
                "GIT_ASKPASS": "echo",
            },
        )
        return True, "Repository is reachable and credentials are valid."
    except subprocess.TimeoutExpired:
        return False, "Repository test timed out while connecting."
    except subprocess.CalledProcessError as exc:
        error = exc.stderr.decode(errors="replace").strip() or exc.stdout.decode(errors="replace").strip()
        return False, redact_access_token(error or "Repository access test failed.", access_token)


def _test_repo_access(project: Project) -> tuple[bool, str]:
    return _test_repo_access_values(
        project.repo_url, project.default_branch, project_access_token(project)
    )


async def _project_or_404(project_id: str, ws: Workspace, session: AsyncSession) -> Project:
    project = await session.get(Project, project_id)
    if not project or project.workspace_id != ws.id:
        raise HTTPException(404, "Project not found")
    return project


@router.get("", response_model=list[ProjectOut])
async def list_projects(
    ws: Workspace = Depends(workspace), session: AsyncSession = Depends(db_session)
) -> list[ProjectOut]:
    res = await session.execute(
        select(Project).where(Project.workspace_id == ws.id).order_by(Project.created_at)
    )
    return [_project_out(p) for p in res.scalars()]


@router.post("", response_model=ProjectOut, status_code=201)
async def create_project(
    payload: ProjectIn,
    ws: Workspace = Depends(workspace),
    session: AsyncSession = Depends(db_session),
) -> ProjectOut:
    project_data = payload.model_dump(exclude={"access_token"})
    project = Project(workspace_id=ws.id, **project_data)
    _apply_access_token(project, payload)
    session.add(project)
    await session.commit()
    await session.refresh(project)
    repo_introspector.invalidate(project.id)
    return _project_out(project)


@router.get("/{project_id}", response_model=ProjectOut)
async def get_project(
    project_id: str,
    ws: Workspace = Depends(workspace),
    session: AsyncSession = Depends(db_session),
) -> ProjectOut:
    project = await _project_or_404(project_id, ws, session)
    return _project_out(project)


@router.put("/{project_id}", response_model=ProjectOut)
async def update_project(
    project_id: str,
    payload: ProjectIn,
    ws: Workspace = Depends(workspace),
    session: AsyncSession = Depends(db_session),
) -> ProjectOut:
    project = await _project_or_404(project_id, ws, session)
    repo_introspector.invalidate(project.id)
    token_is_explicitly_set = "access_token" in payload.model_fields_set
    for key, value in payload.model_dump(exclude={"access_token"}).items():
        if key == "config":
            next_config = dict(value or {})
            existing_token = (project.config or {}).get(PROJECT_ACCESS_TOKEN_KEY)
            if not token_is_explicitly_set and isinstance(existing_token, str) and existing_token.strip():
                next_config[PROJECT_ACCESS_TOKEN_KEY] = existing_token
            setattr(project, key, next_config)
            continue
        setattr(project, key, value)
    _apply_access_token(project, payload)
    await session.commit()
    await session.refresh(project)
    return _project_out(project)


@router.delete("/{project_id}", status_code=204)
async def delete_project(
    project_id: str,
    ws: Workspace = Depends(workspace),
    session: AsyncSession = Depends(db_session),
) -> None:
    project = await _project_or_404(project_id, ws, session)
    repo_introspector.invalidate(project.id)
    await session.delete(project)
    await session.commit()


@router.get("/{project_id}/introspect", response_model=ProjectIntrospectionOut)
async def introspect_project(
    project_id: str,
    ws: Workspace = Depends(workspace),
    session: AsyncSession = Depends(db_session),
) -> ProjectIntrospectionOut:
    project = await _project_or_404(project_id, ws, session)
    suggestions = await anyio.to_thread.run_sync(
        lambda: introspect_project_commands(project)
    )
    return ProjectIntrospectionOut(**suggestions.as_dict())


@router.post("/{project_id}/test-repo", response_model=ProjectRepoTestOut)
async def test_project_repo_access(
    project_id: str,
    ws: Workspace = Depends(workspace),
    session: AsyncSession = Depends(db_session),
) -> ProjectRepoTestOut:
    project = await _project_or_404(project_id, ws, session)
    ok, message = await anyio.to_thread.run_sync(lambda: _test_repo_access(project))
    return ProjectRepoTestOut(ok=ok, message=message)


@router.post("/test-repo", response_model=ProjectRepoTestOut)
async def test_repo_access_for_draft(payload: ProjectRepoTestIn) -> ProjectRepoTestOut:
    token = (payload.access_token or "").strip() or None
    ok, message = await anyio.to_thread.run_sync(
        lambda: _test_repo_access_values(payload.repo_url, payload.default_branch, token)
    )
    return ProjectRepoTestOut(ok=ok, message=message)


@router.post("/oauth/github/device/start", response_model=GitHubDeviceOAuthStartOut)
async def github_device_oauth_start(payload: GitHubDeviceOAuthStartIn) -> GitHubDeviceOAuthStartOut:
    if not settings.github_oauth_client_id:
        raise HTTPException(
            400,
            "GitHub OAuth is not configured. Set OUROBOROS_GITHUB_OAUTH_CLIENT_ID in the API environment.",
        )
    if not _is_github_repo_url(payload.repo_url):
        raise HTTPException(400, "GitHub OAuth token flow is only supported for GitHub repository URLs")

    async with httpx.AsyncClient(timeout=15.0) as client:
        res = await client.post(
            "https://github.com/login/device/code",
            data={"client_id": settings.github_oauth_client_id, "scope": settings.github_oauth_scope},
            headers={"Accept": "application/json"},
        )
    if res.status_code >= 400:
        raise HTTPException(400, f"GitHub device-code request failed: {res.text[:500]}")

    data = res.json()
    return GitHubDeviceOAuthStartOut(
        device_code=data["device_code"],
        user_code=data["user_code"],
        verification_uri=data.get("verification_uri") or data.get("verification_uri_complete"),
        expires_in=data.get("expires_in", 900),
        interval=data.get("interval", 5),
    )


@router.post("/oauth/github/device/poll", response_model=GitHubDeviceOAuthPollOut)
async def github_device_oauth_poll(payload: GitHubDeviceOAuthPollIn) -> GitHubDeviceOAuthPollOut:
    if not settings.github_oauth_client_id:
        raise HTTPException(
            400,
            "GitHub OAuth is not configured. Set OUROBOROS_GITHUB_OAUTH_CLIENT_ID in the API environment.",
        )
    async with httpx.AsyncClient(timeout=15.0) as client:
        res = await client.post(
            "https://github.com/login/oauth/access_token",
            data={
                "client_id": settings.github_oauth_client_id,
                "device_code": payload.device_code,
                "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
            },
            headers={"Accept": "application/json"},
        )
    if res.status_code >= 400:
        raise HTTPException(400, f"GitHub token exchange failed: {res.text[:500]}")

    data = res.json()
    error = data.get("error")
    if error:
        if error in {"authorization_pending", "slow_down"}:
            return GitHubDeviceOAuthPollOut(
                status="pending",
                error=error,
                error_description=data.get("error_description"),
                interval=data.get("interval"),
            )
        return GitHubDeviceOAuthPollOut(
            status="error",
            error=error,
            error_description=data.get("error_description"),
        )

    token = data.get("access_token")
    if not token:
        return GitHubDeviceOAuthPollOut(status="error", error="missing_access_token")
    return GitHubDeviceOAuthPollOut(status="authorized", access_token=token)
