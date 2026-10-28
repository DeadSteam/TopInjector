"""Integration group CRUD and server management.

Integration groups represent a logical pool of servers that projects can be assigned to.
Each group has an RPM limit, project count cap, IP whitelist, and may contain servers
running different software (Alpine, Monstro, Portal, Fantom).
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from services.auth_service.domain.models import User
from services.project_service.domain.models import IntegrationGroup, IntegrationServer, Project
from shared.auth.jwt_utils import get_current_user
from shared.database.session import get_session

router = APIRouter(tags=["integration-groups"])


# --------------------------------------------------------------------------- #
#  Helpers                                                                    #
# --------------------------------------------------------------------------- #

def _group_json(g: IntegrationGroup) -> dict:
    return {
        "id": str(g.id),
        "name": g.name,
        "max_projects": g.max_projects,
        "current_project_count": g.current_project_count,
        "rpm_limit": g.rpm_limit,
        "ip_whitelist": g.ip_whitelist or [],
        "use_reserved": g.use_reserved,
        "is_public": g.is_public,
        "is_active": g.is_active,
        "server_count": len(g.servers) if g.servers else 0,
        "created_at": g.created_at.isoformat() if g.created_at else None,
    }


def _server_json(s: IntegrationServer) -> dict:
    return {
        "id": str(s.id),
        "name": s.name,
        "ip_address": s.ip_address,
        "software_type": s.software_type,
        "is_active": s.is_active,
        "max_queries_per_minute": s.max_queries_per_minute,
        "notes": s.notes,
        "created_at": s.created_at.isoformat() if s.created_at else None,
    }


# --------------------------------------------------------------------------- #
#  Integration groups — CRUD                                                  #
# --------------------------------------------------------------------------- #

@router.get("/integration-groups")
async def list_groups(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """List all integration groups owned by the current user."""
    groups = (await session.execute(
        select(IntegrationGroup)
        .where(IntegrationGroup.user_id == user.id)
        .order_by(IntegrationGroup.name)
    )).scalars().all()
    return {"groups": [_group_json(g) for g in groups]}


@router.post("/integration-groups")
async def create_group(
    body: dict,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Create a new integration group."""
    name = body.get("name", "").strip()
    if not name or len(name) > 200:
        raise HTTPException(status_code=422, detail="name is required (max 200 chars)")

    # Check plan limits for max groups (simple count check against plan)
    from services.project_service.domain.plans import UserPlan as UpModel, Plan as PlanModel
    up = (await session.execute(
        select(UpModel).where(UpModel.user_id == user.id)
    )).scalar_one_or_none()
    if up:
        plan = (await session.execute(
            select(PlanModel).where(PlanModel.id == up.plan_id)
        )).scalar_one()
        group_count = (await session.execute(
            select(func.count()).select_from(IntegrationGroup).where(
                IntegrationGroup.user_id == user.id
            )
        )).scalar() or 0
        if group_count >= plan.max_groups:
            raise HTTPException(
                status_code=403,
                detail=f"Plan limit: {plan.max_groups} integration groups maximum",
            )

    existing = (await session.execute(
        select(IntegrationGroup).where(
            IntegrationGroup.user_id == user.id,
            IntegrationGroup.name == name,
        )
    )).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="Integration group with this name already exists")

    g = IntegrationGroup(
        user_id=user.id,
        name=name,
        max_projects=body.get("max_projects", 10),
        rpm_limit=body.get("rpm_limit", 300),
        ip_whitelist=body.get("ip_whitelist", []),
        use_reserved=bool(body.get("use_reserved", False)),
        is_public=bool(body.get("is_public", False)),
    )
    session.add(g)
    await session.commit()
    await session.refresh(g)
    return _group_json(g)


@router.put("/integration-groups/{group_id}")
async def update_group(
    group_id: UUID,
    body: dict,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Update an integration group."""
    g = await session.get(IntegrationGroup, group_id)
    if g is None or g.user_id != user.id:
        raise HTTPException(status_code=404, detail="Integration group not found")

    if "name" in body:
        name = body["name"].strip()
        if not name or len(name) > 200:
            raise HTTPException(status_code=422, detail="name is required (max 200 chars)")
        g.name = name

    for field in ("max_projects", "rpm_limit"):
        if field in body:
            setattr(g, field, body[field])

    for field in ("ip_whitelist",):
        if field in body:
            setattr(g, field, body[field])

    for field in ("use_reserved", "is_public", "is_active"):
        if field in body:
            setattr(g, field, bool(body[field]))

    await session.commit()
    return _group_json(g)


@router.delete("/integration-groups/{group_id}")
async def delete_group(
    group_id: UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Delete an integration group (projects unlinked, servers cascaded)."""
    g = await session.get(IntegrationGroup, group_id)
    if g is None or g.user_id != user.id:
        raise HTTPException(status_code=404, detail="Integration group not found")

    # Unlink any projects assigned to this group
    await session.execute(
        Project.__table__.update()
        .where(Project.integration_group_id == group_id)
        .values(integration_group_id=None)
    )
    await g.delete()
    await session.commit()


@router.get("/integration-groups/{group_id}")
async def get_group(
    group_id: UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Get integration group with servers detail."""
    g = await session.get(IntegrationGroup, group_id)
    if g is None or g.user_id != user.id:
        raise HTTPException(status_code=404, detail="Integration group not found")
    return _group_json(g)


# --------------------------------------------------------------------------- #
#  Integration servers — CRUD                                                 #
# --------------------------------------------------------------------------- #

@router.get("/integration-groups/{group_id}/servers")
async def list_servers(
    group_id: UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """List servers within an integration group."""
    g = await session.get(IntegrationGroup, group_id)
    if g is None or g.user_id != user.id:
        raise HTTPException(status_code=404, detail="Integration group not found")

    servers = (await session.execute(
        select(IntegrationServer)
        .where(IntegrationServer.group_id == group_id)
        .order_by(IntegrationServer.name)
    )).scalars().all()
    return {"servers": [_server_json(s) for s in servers]}


@router.post("/integration-groups/{group_id}/servers")
async def create_server(
    group_id: UUID,
    body: dict,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Add a server to an integration group."""
    g = await session.get(IntegrationGroup, group_id)
    if g is None or g.user_id != user.id:
        raise HTTPException(status_code=404, detail="Integration group not found")

    name = body.get("name", "").strip()
    if not name or len(name) > 200:
        raise HTTPException(status_code=422, detail="Server name is required (max 200 chars)")

    s = IntegrationServer(
        group_id=g.id,
        name=name,
        ip_address=body.get("ip_address"),
        software_type=body.get("software_type", "portal"),
        max_queries_per_minute=body.get("max_queries_per_minute", 60),
        notes=body.get("notes"),
    )
    session.add(s)
    await session.commit()
    await session.refresh(s)
    return _server_json(s)


@router.put("/integration-groups/{group_id}/servers/{server_id}")
async def update_server(
    group_id: UUID,
    server_id: UUID,
    body: dict,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Update a server."""
    s = await session.get(IntegrationServer, server_id)
    if s is None or s.group_id != group_id:
        raise HTTPException(status_code=404, detail="Server not found")

    for field in ("name", "ip_address", "software_type", "notes"):
        if field in body:
            setattr(s, field, body[field])

    for field in ("is_active",):
        if field in body:
            setattr(s, field, bool(body[field]))

    for field in ("max_queries_per_minute",):
        if field in body:
            setattr(s, field, body[field])

    await session.commit()
    return _server_json(s)


@router.delete("/integration-groups/{group_id}/servers/{server_id}")
async def delete_server(
    group_id: UUID,
    server_id: UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Delete a server."""
    s = await session.get(IntegrationServer, server_id)
    if s is None or s.group_id != group_id:
        raise HTTPException(status_code=404, detail="Server not found")

    await s.delete()
    await session.commit()


# --------------------------------------------------------------------------- #
#  Projects — integration_group filter (on existing projects endpoint)         #
# --------------------------------------------------------------------------- #

@router.get("/projects/integrations")
async def list_projects_by_integration(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """List projects grouped by their integration group — used for sidebar filtering."""
    groups = (await session.execute(
        select(IntegrationGroup)
        .where(
            IntegrationGroup.user_id == user.id,
            IntegrationGroup.is_active == True,  # noqa: E712
        )
        .options()  # eager load — will be resolved at route level
    )).scalars().all()

    result = []
    for g in groups:
        projects = (await session.execute(
            select(Project)
            .where(Project.integration_group_id == g.id)
            .order_by(Project.name)
        )).scalars().all()
        result.append({
            "group": _group_json(g),
            "projects": [
                {
                    "id": str(p.id),
                    "name": p.name,
                    "domain": p.domain,
                    "is_active": p.is_active,
                }
                for p in projects
            ],
        })
    return result
