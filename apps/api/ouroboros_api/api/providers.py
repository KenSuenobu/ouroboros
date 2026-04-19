"""Provider CRUD + chat-test + model refresh."""

from __future__ import annotations

from datetime import UTC, datetime

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
