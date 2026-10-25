"""Panel API access control: who is calling, and which projects they may read or change.

Owners can do anything with their projects. Delegates (ProjectDelegate) can read; those
with role "edit" can also change the project, but owner-only actions stay with the owner.
"""

from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import Select, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.auth.jwt_utils import decode_access_token
from shared.database.session import get_session
from services.project_service.domain.models import Project, ProjectDelegate

SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


def request_user_id(request: Request) -> UUID:
    """Return the caller's user id from the Bearer token, or raise 401.

    Read-only requests may also authenticate with the httpOnly ``token`` cookie set at login,
    because EventSource (the queue SSE feed) can't send an Authorization header.
    """
    auth = request.headers.get("authorization", "")
    token = auth[7:] if auth.startswith("Bearer ") else None
    if token is None and request.method in SAFE_METHODS:
        token = request.cookies.get("token")
    user_id = decode_access_token(token) if token else None
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user_id


def accessible_project_ids(user_id: UUID) -> Select:
    """Ids of projects the user owns or was delegated (any role)."""
    delegated = select(ProjectDelegate.project_id).where(ProjectDelegate.delegate_user_id == user_id)
    return select(Project.id).where(or_(Project.user_id == user_id, Project.id.in_(delegated)))


def editable_project_ids(user_id: UUID) -> Select:
    """Ids of projects the user owns or was delegated with the "edit" role."""
    delegated = select(ProjectDelegate.project_id).where(
        ProjectDelegate.delegate_user_id == user_id, ProjectDelegate.role == "edit"
    )
    return select(Project.id).where(or_(Project.user_id == user_id, Project.id.in_(delegated)))


async def check_project_access(
    session: AsyncSession,
    project_id: UUID | str,
    user_id: UUID,
    *,
    write: bool = False,
    owner_only: bool = False,
) -> Project:
    """Return the project if the user may access it; 404 if they can't see it, 403 if they can't change it."""
    try:
        pid = project_id if isinstance(project_id, UUID) else UUID(str(project_id))
    except ValueError:
        raise HTTPException(status_code=404, detail="Project not found")

    project = await session.get(Project, pid)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    if project.user_id == user_id:
        return project

    role = (
        await session.execute(
            select(ProjectDelegate.role).where(
                ProjectDelegate.project_id == pid, ProjectDelegate.delegate_user_id == user_id
            )
        )
    ).scalar_one_or_none()
    if role is None:
        raise HTTPException(status_code=404, detail="Project not found")
    if owner_only or (write and role != "edit"):
        raise HTTPException(status_code=403, detail="Not allowed for delegated access")
    return project


def _path_project_id(request: Request) -> str | None:
    return request.path_params.get("project_id") or request.path_params.get("id")


async def authorize_project_path(
    request: Request,
    user_id: UUID = Depends(request_user_id),
    session: AsyncSession = Depends(get_session),
) -> None:
    """Router dependency: require auth and check access to the project named in the path, if any."""
    project_id = _path_project_id(request)
    if project_id is not None:
        await check_project_access(session, project_id, user_id, write=request.method not in SAFE_METHODS)


async def require_project_owner(
    request: Request,
    user_id: UUID = Depends(request_user_id),
    session: AsyncSession = Depends(get_session),
) -> None:
    """Route dependency for actions only the owner may take (delete, delegates, balance)."""
    await check_project_access(session, _path_project_id(request), user_id, owner_only=True)
