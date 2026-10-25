"""External rank-tracking data-source accounts (Yandex Webmaster, XMLRiver, XMLStock).

Each account belongs to one user; Yandex Webmaster accounts can list confirmed domains.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from services.auth_service.domain.models import User
from services.project_service.domain.external_services import (
    EXTERNAL_SERVICE_TYPES,
    ExternalServiceAccount,
    YandexWebmasterDomain,
)
from shared.auth.jwt_utils import get_current_user
from shared.database.session import get_session
from shared.validation import require_fields

router = APIRouter(tags=["external-services"])


def _account_json(a: ExternalServiceAccount) -> dict:
    return {
        "id": str(a.id),
        "service_type": a.service_type,
        "display_name": a.display_name,
        "config_json": a.config_json or {},
        "is_active": a.is_active,
        "created_at": a.created_at.isoformat() if a.created_at else None,
    }


async def _owned_account(session: AsyncSession, account_id: str, user_id: UUID) -> ExternalServiceAccount:
    try:
        aid = UUID(account_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Account not found")
    account = (await session.execute(
        select(ExternalServiceAccount).where(
            ExternalServiceAccount.id == aid, ExternalServiceAccount.user_id == user_id
        )
    )).scalar_one_or_none()
    if account is None:
        raise HTTPException(status_code=404, detail="Account not found")
    return account


@router.get("")
async def list_accounts(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """List the current user's external-service accounts."""
    rows = (await session.execute(
        select(ExternalServiceAccount)
        .where(ExternalServiceAccount.user_id == user.id)
        .order_by(ExternalServiceAccount.created_at)
    )).scalars().all()
    return {"accounts": [_account_json(a) for a in rows]}


@router.post("")
async def create_account(
    body: dict,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Connect a new external-service account."""
    require_fields(body, "service_type", "display_name")
    service_type = str(body["service_type"]).strip().lower()
    if service_type not in EXTERNAL_SERVICE_TYPES:
        raise HTTPException(
            status_code=422,
            detail=f"service_type must be one of: {', '.join(sorted(EXTERNAL_SERVICE_TYPES))}",
        )
    config = body.get("config_json") or {}
    if not isinstance(config, dict):
        raise HTTPException(status_code=422, detail="config_json must be an object")

    account = ExternalServiceAccount(
        user_id=user.id,
        service_type=service_type,
        display_name=str(body["display_name"]),
        config_json=config,
        is_active=bool(body.get("is_active", True)),
    )
    session.add(account)
    await session.commit()
    await session.refresh(account)
    return _account_json(account)


@router.put("/{account_id}")
async def update_account(
    account_id: str,
    body: dict,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Update display name, config or active flag of an account."""
    account = await _owned_account(session, account_id, user.id)
    if "display_name" in body:
        account.display_name = str(body["display_name"])
    if "config_json" in body:
        if not isinstance(body["config_json"], dict):
            raise HTTPException(status_code=422, detail="config_json must be an object")
        account.config_json = body["config_json"]
    if "is_active" in body:
        account.is_active = bool(body["is_active"])
    await session.commit()
    await session.refresh(account)
    return _account_json(account)


@router.delete("/{account_id}")
async def delete_account(
    account_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Delete an account (and its domains)."""
    account = await _owned_account(session, account_id, user.id)
    await session.delete(account)
    await session.commit()
    return {"deleted": True}


@router.get("/{account_id}/domains")
async def list_domains(
    account_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """List domains confirmed under a Yandex Webmaster account."""
    account = await _owned_account(session, account_id, user.id)
    rows = (await session.execute(
        select(YandexWebmasterDomain)
        .where(YandexWebmasterDomain.service_account_id == account.id)
        .order_by(YandexWebmasterDomain.domain)
    )).scalars().all()
    return {
        "domains": [
            {
                "id": str(d.id),
                "domain": d.domain,
                "is_confirmed": d.is_confirmed,
                "last_sync_at": d.last_sync_at.isoformat() if d.last_sync_at else None,
            }
            for d in rows
        ]
    }


@router.post("/{account_id}/domains")
async def add_domain(
    account_id: str,
    body: dict,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Add a domain to a Yandex Webmaster account."""
    account = await _owned_account(session, account_id, user.id)
    require_fields(body, "domain")
    domain = YandexWebmasterDomain(
        service_account_id=account.id,
        domain=str(body["domain"]).strip(),
        is_confirmed=bool(body.get("is_confirmed", True)),
    )
    session.add(domain)
    await session.commit()
    await session.refresh(domain)
    return {"id": str(domain.id), "domain": domain.domain, "is_confirmed": domain.is_confirmed}
