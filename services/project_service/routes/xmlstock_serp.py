"""XMLStock SERP scraping API — query search-engine results via XMLStock accounts.

Endpoints:
- GET  /xmlstock-serp/accounts      — list XMLStock accounts
- POST /xmlstock-serp/search         — single SERP query (returns top results)
- POST /xmlstock-serp/batch-search   — batch SERP queries (multiple keywords at once)
- GET  /xmlstock-serp/history        — past search history for the user
"""

from datetime import datetime, timezone
from uuid import UUID, uuid4

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from services.auth_service.domain.models import User
from services.project_service.domain.external_services import ExternalServiceAccount
from shared.auth.jwt_utils import get_current_user
from shared.database.session import get_session

router = APIRouter(tags=["xmlstock-serp"])


@router.get("/xmlstock-serp/accounts")
async def list_xmlstock_accounts(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """List active XMLStock service accounts."""
    rows = (await session.execute(
        select(ExternalServiceAccount)
        .where(
            ExternalServiceAccount.user_id == user.id,
            ExternalServiceAccount.service_type == "xmlstock",
            ExternalServiceAccount.is_active.is_(True),
        )
    )).scalars().all()
    return {
        "accounts": [
            {
                "id": str(a.id),
                "display_name": a.display_name,
                "config": a.config_json or {},
            }
            for a in rows
        ]
    }


@router.post("/xmlstock-serp/search")
async def search_serp(
    body: dict,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Search SERP via an XMLStock account.

    Body: { "account_id": "...", "query": "keyword", "engine": "yandex" }
    Returns SERP results with positions, URLs, titles, descriptions.
    """
    require_keys = ["account_id", "query"]
    for key in require_keys:
        if key not in body:
            raise HTTPException(status_code=422, detail=f"Required field: {key}")

    require_keys = ["account_id", "query"]
    for key in require_keys:
        if key not in body:
            raise HTTPException(status_code=422, detail=f"Required field: {key}")

    account_id = UUID(body["account_id"])
    query = str(body["query"]).strip()
    engine = str(body.get("engine", "yandex")).lower()
    geo = body.get("geo")  # optional: {"city": "...", "region": "..."}

    # Validate account ownership and type
    account = (await session.execute(
        select(ExternalServiceAccount)
        .where(
            ExternalServiceAccount.id == account_id,
            ExternalServiceAccount.user_id == user.id,
            ExternalServiceAccount.service_type == "xmlstock",
            ExternalServiceAccount.is_active.is_(True),
        )
    )).scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="XMLStock account not found or inactive")

    api_key = (account.config_json or {}).get("api_key")
    if not api_key:
        raise HTTPException(status_code=422, detail="XMLStock account has no API key configured")

    # Build XMLStock API request parameters
    params: dict = {
        "q": query,
        "engine": engine,
        "apikey": api_key,
    }
    if geo:
        if isinstance(geo, dict):
            if "city" in geo:
                params["city"] = str(geo["city"])
            if "region" in geo:
                params["region"] = str(geo["region"])
            if "geo_id" in geo:
                params["geo_id"] = str(geo["geo_id"])

    limit = body.get("limit", 100)
    params["count"] = min(int(limit), 100)

    # Call XMLStock API
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get("https://api.xmlstock.net/v1/search", params=params)
            if resp.status_code != 200:
                raise HTTPException(
                    status_code=502,
                    detail=f"XMLStock API error ({resp.status_code}): {resp.text[:500]}",
                )
            data = resp.json()
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"XMLStock request failed: {str(e)}")

    # Parse response into standard SERP result format
    results = []
    organic = data.get("organic_results") or data.get("results") or []
    for idx, item in enumerate(organic, start=1):
        results.append({
            "position": idx,
            "title": item.get("title", "") or item.get("html_title", ""),
            "url": item.get("url", "") or item.get("link", ""),
            "description": item.get("description", "") or item.get("snippet", ""),
            "domain": "",  # optionally parse from URL
        })

    return {
        "query": query,
        "engine": engine,
        "total_results": data.get("search_information", {}).get("total_results") or len(results),
        "results": results,
    }


@router.post("/xmlstock-serp/batch-search")
async def batch_search_serp(
    body: dict,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Batch SERP search for multiple keywords via XMLStock.

    Body: { "account_id": "...", "queries": ["kw1", "kw2"], "engine": "yandex" }
    Returns grouped results with positions per query.
    """
    account_id_str = body.get("account_id")
    queries = body.get("queries")

    if not account_id_str:
        raise HTTPException(status_code=422, detail="Required field: account_id")
    if not queries or not isinstance(queries, list):
        raise HTTPException(status_code=422, detail="Required field: queries (non-empty array)")

    try:
        account_id = UUID(account_id_str)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid account_id")

    # Validate account
    account = (await session.execute(
        select(ExternalServiceAccount).where(
            ExternalServiceAccount.id == account_id,
            ExternalServiceAccount.user_id == user.id,
            ExternalServiceAccount.service_type == "xmlstock",
            ExternalServiceAccount.is_active.is_(True),
        )
    )).scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="XMLStock account not found or inactive")

    api_key = (account.config_json or {}).get("api_key")
    if not api_key:
        raise HTTPException(status_code=422, detail="XMLStock account has no API key configured")

    engine = str(body.get("engine", "yandex")).lower()
    geo = body.get("geo")
    limit = min(int(body.get("limit", 100)), 100)

    results_by_query: dict[str, list] = {}
    errors: list[dict] = []

    async with httpx.AsyncClient(timeout=60) as client:
        for kw in queries[:50]:  # max 50 queries per batch
            kw_str = str(kw).strip()
            if not kw_str:
                continue
            params = {
                "q": kw_str,
                "engine": engine,
                "apikey": api_key,
                "count": limit,
            }
            if geo and isinstance(geo, dict):
                if "city" in geo:
                    params["city"] = str(geo["city"])
                if "region" in geo:
                    params["region"] = str(geo["region"])

            try:
                resp = await client.get("https://api.xmlstock.net/v1/search", params=params)
                if resp.status_code != 200:
                    errors.append({"query": kw_str, "error": f"XMLStock error {resp.status_code}"})
                    continue
                data = resp.json()
            except httpx.HTTPError:
                errors.append({"query": kw_str, "error": "Request failed"})
                continue

            organic = data.get("organic_results") or data.get("results") or []
            parsed = []
            for idx, item in enumerate(organic, start=1):
                parsed.append({
                    "position": idx,
                    "title": item.get("title", "") or item.get("html_title", ""),
                    "url": item.get("url", "") or item.get("link", ""),
                    "description": item.get("description", "") or item.get("snippet", ""),
                })
            results_by_query[kw_str] = parsed

    return {
        "queries_processed": len(results_by_query) + len(errors),
        "results": results_by_query,
        "errors": errors,
    }


@router.get("/xmlstock-serp/history")
async def serp_search_history(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    limit: int = 50,
):
    """Return recent SERP search history (stored in user.external_services)."""
    external = user.external_services or {}
    history = external.get("xmlstock_serp_history", [])
    return {"history": history[-limit:]}


@router.post("/xmlstock-serp/save-history")
async def save_serp_history(
    body: dict,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Save SERP search results to user's local history for later reference.

    Body: { "query": "...", "results": [...], "engine": "yandex" }
    """
    query = body.get("query")
    if not query:
        raise HTTPException(status_code=422, detail="Required field: query")

    external = user.external_services or {}
    history = external.get("xmlstock_serp_history", [])

    entry = {
        "id": str(uuid4()),
        "query": str(query),
        "engine": str(body.get("engine", "yandex")),
        "results_count": len(body.get("results", [])),
        "saved_at": datetime.now(timezone.utc).isoformat(),
    }
    history.insert(0, entry)
    # Keep only last 500 entries
    user.external_services = {**external, "xmlstock_serp_history": history[:500]}
    await session.commit()

    return {"saved": True, "total": len(history)}
