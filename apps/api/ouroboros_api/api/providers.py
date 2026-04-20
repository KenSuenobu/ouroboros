"""Provider CRUD + chat-test + model refresh."""

from __future__ import annotations

from datetime import UTC, datetime

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from ..adapters.base import LLMMessage, ResolvedModel
from ..adapters.registry import providers
from ..db.models import Provider, ProviderModel, Workspace
from ..secrets import secrets
from .deps import db_session, workspace
from .schemas import (
    ProviderChatRequest,
    ProviderChatResponse,
    ProviderHealthOut,
    ProviderIn,
    ProviderModelOut,
    ProviderOut,
)

router = APIRouter(prefix="/api/providers", tags=["providers"])


def _to_out(p: Provider) -> ProviderOut:
    return ProviderOut(
        id=p.id,
        workspace_id=p.workspace_id,
        name=p.name,
        kind=p.kind,
        base_url=p.base_url,
        has_api_key=bool(p.api_key_secret_ref),
        config=p.config,
        enabled=p.enabled,
        last_health_status=p.last_health_status,
        last_health_error=p.last_health_error,
        last_health_checked_at=p.last_health_checked_at,
    )


def _secret_ref(workspace_id: str, provider_id: str) -> str:
    return f"workspace:{workspace_id}:provider:{provider_id}:api_key"


def _resolve_model(p: Provider, model_id: str | None = None) -> ResolvedModel:
    api_key = secrets.get(p.api_key_secret_ref) if p.api_key_secret_ref else None
    return ResolvedModel(
        provider_id=p.id,
        provider_kind=p.kind,
        model_id=model_id or "",
        base_url=p.base_url,
        api_key=api_key,
        extra=dict(p.config or {}),
    )


def _error_text(response: httpx.Response) -> str:
    text = response.text.strip()
    if text:
        return text[:1000]
    return f"{response.status_code} {response.reason_phrase}"


def _status_from_http_error(exc: Exception) -> str:
    if isinstance(exc, httpx.HTTPStatusError):
        if exc.response.status_code in {401, 403}:
            return "unauthorized"
        return "unreachable"
    if isinstance(exc, httpx.RequestError):
        return "unreachable"
    return "unreachable"


async def _probe_health(provider: Provider) -> tuple[str, str | None]:
    resolved = _resolve_model(provider)
    try:
        if provider.kind == "ollama":
            base_url = (provider.base_url or "http://localhost:11434").rstrip("/")
            async with httpx.AsyncClient(base_url=base_url, timeout=10.0) as client:
                res = await client.get("/api/tags")
                res.raise_for_status()
                models = (res.json() or {}).get("models", [])
                if not models:
                    return "no-models", "No models returned by /api/tags"
                return "ok", None

        if provider.kind == "anthropic":
            base_url = (provider.base_url or "https://api.anthropic.com").rstrip("/")
            headers = {
                "x-api-key": resolved.api_key or "",
                "anthropic-version": "2023-06-01",
            }
            async with httpx.AsyncClient(base_url=base_url, headers=headers, timeout=10.0) as client:
                res = await client.head("/v1/messages")
                if res.status_code in {401, 403}:
                    return "unauthorized", _error_text(res)
                if res.status_code >= 400 and res.status_code != 405:
                    return "unreachable", _error_text(res)
                return "ok", None

        if provider.kind == "github_models":
            base_url = (provider.base_url or "https://models.github.ai").rstrip("/")
            headers = {
                "Authorization": f"Bearer {resolved.api_key or ''}",
                "Accept": "application/json",
            }
            async with httpx.AsyncClient(base_url=base_url, headers=headers, timeout=10.0) as client:
                res = await client.get("/catalog/models")
                if res.status_code in {401, 403}:
                    return "unauthorized", _error_text(res)
                res.raise_for_status()
                models = res.json() or []
                if not models:
                    return "no-models", "No models returned by /catalog/models"
                return "ok", None

    except Exception as exc:
        status = _status_from_http_error(exc)
        if isinstance(exc, httpx.HTTPStatusError):
            return status, _error_text(exc.response)
        return status, str(exc)

    return "ok", None


async def _run_health_probe(provider: Provider) -> ProviderHealthOut:
    status, error = await _probe_health(provider)
    checked_at = datetime.now(UTC)
    provider.last_health_status = status
    provider.last_health_error = error
    provider.last_health_checked_at = checked_at
    return ProviderHealthOut(provider_id=provider.id, status=status, error=error, checked_at=checked_at)


@router.get("", response_model=list[ProviderOut])
async def list_providers(
    ws: Workspace = Depends(workspace), session: AsyncSession = Depends(db_session)
) -> list[ProviderOut]:
    res = await session.execute(
        select(Provider).where(Provider.workspace_id == ws.id).order_by(Provider.created_at)
    )
    return [_to_out(p) for p in res.scalars()]


@router.post("", response_model=ProviderOut, status_code=201)
async def create_provider(
    payload: ProviderIn,
    ws: Workspace = Depends(workspace),
    session: AsyncSession = Depends(db_session),
) -> ProviderOut:
    if payload.kind not in providers().kinds() and payload.kind not in {"opencode", "gh_copilot"}:
        raise HTTPException(400, f"Unknown provider kind: {payload.kind}")
    provider = Provider(
        workspace_id=ws.id,
        name=payload.name,
        kind=payload.kind,
        base_url=payload.base_url,
        config=payload.config,
        enabled=payload.enabled,
    )
    session.add(provider)
    await session.flush()
    if payload.api_key:
        ref = _secret_ref(ws.id, provider.id)
        secrets.set(ref, payload.api_key)
        provider.api_key_secret_ref = ref
    await _run_health_probe(provider)
    await session.commit()
    await session.refresh(provider)
    return _to_out(provider)


@router.get("/{provider_id}", response_model=ProviderOut)
async def get_provider(
    provider_id: str,
    ws: Workspace = Depends(workspace),
    session: AsyncSession = Depends(db_session),
) -> ProviderOut:
    provider = await session.get(Provider, provider_id)
    if not provider or provider.workspace_id != ws.id:
        raise HTTPException(404, "Provider not found")
    return _to_out(provider)


@router.put("/{provider_id}", response_model=ProviderOut)
async def update_provider(
    provider_id: str,
    payload: ProviderIn,
    ws: Workspace = Depends(workspace),
    session: AsyncSession = Depends(db_session),
) -> ProviderOut:
    provider = await session.get(Provider, provider_id)
    if not provider or provider.workspace_id != ws.id:
        raise HTTPException(404, "Provider not found")
    provider.name = payload.name
    provider.kind = payload.kind
    provider.base_url = payload.base_url
    provider.config = payload.config
    provider.enabled = payload.enabled
    if payload.api_key:
        ref = provider.api_key_secret_ref or _secret_ref(ws.id, provider.id)
        secrets.set(ref, payload.api_key)
        provider.api_key_secret_ref = ref
    await _run_health_probe(provider)
    await session.commit()
    await session.refresh(provider)
    return _to_out(provider)


@router.delete("/{provider_id}", status_code=204)
async def delete_provider(
    provider_id: str,
    ws: Workspace = Depends(workspace),
    session: AsyncSession = Depends(db_session),
) -> None:
    provider = await session.get(Provider, provider_id)
    if not provider or provider.workspace_id != ws.id:
        raise HTTPException(404, "Provider not found")
    if provider.api_key_secret_ref:
        secrets.delete(provider.api_key_secret_ref)
    await session.delete(provider)
    await session.commit()


@router.get("/{provider_id}/models", response_model=list[ProviderModelOut])
async def list_models(
    provider_id: str,
    ws: Workspace = Depends(workspace),
    session: AsyncSession = Depends(db_session),
) -> list[ProviderModelOut]:
    provider = await session.get(Provider, provider_id)
    if not provider or provider.workspace_id != ws.id:
        raise HTTPException(404, "Provider not found")
    res = await session.execute(
        select(ProviderModel).where(ProviderModel.provider_id == provider.id).order_by(ProviderModel.model_id)
    )
    return [ProviderModelOut.model_validate(m) for m in res.scalars()]


@router.get("/{provider_id}/health", response_model=ProviderHealthOut)
async def provider_health(
    provider_id: str,
    ws: Workspace = Depends(workspace),
    session: AsyncSession = Depends(db_session),
) -> ProviderHealthOut:
    provider = await session.get(Provider, provider_id)
    if not provider or provider.workspace_id != ws.id:
        raise HTTPException(404, "Provider not found")
    result = await _run_health_probe(provider)
    await session.commit()
    return result


@router.post("/{provider_id}/models/refresh", response_model=list[ProviderModelOut])
async def refresh_models(
    provider_id: str,
    ws: Workspace = Depends(workspace),
    session: AsyncSession = Depends(db_session),
) -> list[ProviderModelOut]:
    provider = await session.get(Provider, provider_id)
    if not provider or provider.workspace_id != ws.id:
        raise HTTPException(404, "Provider not found")
    if provider.kind not in providers().kinds():
        raise HTTPException(400, f"Provider kind {provider.kind!r} doesn't support model refresh")

    impl = providers().get(provider.kind)
    resolved = _resolve_model(provider)
    try:
        catalog = await impl.list_models(resolved)
    except Exception as exc:
        raise HTTPException(502, f"Failed to query provider: {exc}") from exc

    now = datetime.now(UTC)
    for entry in catalog:
        stmt = (
            sqlite_insert(ProviderModel)
            .values(
                workspace_id=ws.id,
                provider_id=provider.id,
                model_id=entry["model_id"],
                display_name=entry.get("display_name") or entry["model_id"],
                capabilities=entry.get("capabilities", []),
                context_window=entry.get("context_window"),
                input_cost_per_mtok=entry.get("input_cost_per_mtok"),
                output_cost_per_mtok=entry.get("output_cost_per_mtok"),
                last_seen_at=now,
            )
            .on_conflict_do_update(
                index_elements=["provider_id", "model_id"],
                set_={
                    "display_name": entry.get("display_name") or entry["model_id"],
                    "capabilities": entry.get("capabilities", []),
                    "context_window": entry.get("context_window"),
                    "input_cost_per_mtok": entry.get("input_cost_per_mtok"),
                    "output_cost_per_mtok": entry.get("output_cost_per_mtok"),
                    "last_seen_at": now,
                },
            )
        )
        await session.execute(stmt)
    await session.commit()
    res = await session.execute(
        select(ProviderModel).where(ProviderModel.provider_id == provider.id).order_by(ProviderModel.model_id)
    )
    return [ProviderModelOut.model_validate(m) for m in res.scalars()]


@router.post("/{provider_id}/chat", response_model=ProviderChatResponse)
async def chat(
    provider_id: str,
    payload: ProviderChatRequest,
    ws: Workspace = Depends(workspace),
    session: AsyncSession = Depends(db_session),
) -> ProviderChatResponse:
    provider = await session.get(Provider, provider_id)
    if not provider or provider.workspace_id != ws.id:
        raise HTTPException(404, "Provider not found")
    if provider.kind not in providers().kinds():
        raise HTTPException(400, f"Provider kind {provider.kind!r} cannot chat")

    impl = providers().get(provider.kind)
    resolved = _resolve_model(provider, payload.model_id)
    messages = [LLMMessage(role=m.get("role", "user"), content=m.get("content", "")) for m in payload.messages]
    try:
        result = await impl.complete(resolved, messages, max_tokens=payload.max_tokens)
    except Exception as exc:
        raise HTTPException(502, f"Provider call failed: {exc}") from exc
    return ProviderChatResponse(
        content=result.content,
        model_used=payload.model_id,
        tokens_in=result.tokens_in,
        tokens_out=result.tokens_out,
    )
