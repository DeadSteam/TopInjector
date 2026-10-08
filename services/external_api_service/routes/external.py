"""External API routes (GhostLab-compatible). Base URL: /api/external/v1/ Auth: X-Auth-Token header."""

from fastapi import APIRouter, Depends, Header, HTTPException

router = APIRouter(tags=["external-api"])


# --- Projects --------------------------------------------------------------- #
@router.post("/projects")
async def create_project(body: dict, x_auth_token: str = Header(default=None)):
    return {"id": "proj-1", **body}

@router.get("/projects")
async def list_projects(x_auth_token: str = Header(default=None)):
    return []

@router.put("/projects/{project_id}")
async def update_project(project_id: str, body: dict, x_auth_token: str = Header(default=None)):
    return {"id": project_id, **body}

@router.patch("/projects/{project_id}/status")
async def update_project_status(project_id: str, body: dict, x_auth_token: str = Header(default=None)):
    return {"id": project_id, "is_active": body.get("is_active", True)}

@router.delete("/projects/{project_id}")
async def delete_project(project_id: str, x_auth_token: str = Header(default=None)):
    return {"deleted": True}


# --- Terms ------------------------------------------------------------------ #
@router.post("/terms/upsert")
async def upsert_terms(body: dict, x_auth_token: str = Header(default=None)):
    return {"created": 0, "updated": 0, "deleted": 0}

@router.get("/terms")
async def list_terms(project_id: str = "", x_auth_token: str = Header(default=None)):
    return {"terms": [], "total": 0}


# --- Queue ------------------------------------------------------------------ #
@router.post("/queue/push")
async def push_tasks(body: dict, x_auth_token: str = Header(default=None)):
    return {"queued": 0, "already_exists": 0}

@router.get("/queue")
async def list_queue(project_id: str = "", status: str = "", x_auth_token: str = Header(default=None)):
    return {"tasks": [], "total": 0}

@router.post("/queue/clear")
async def clear_queue(project_id: str, x_auth_token: str = Header(default=None)):
    return {"deleted": 0}

@router.post("/queue/results")
async def submit_results(body: dict, x_auth_token: str = Header(default=None)):
    return {"updated": 0, "errors": []}


# --- Users ------------------------------------------------------------------ #
@router.post("/users")
async def create_user(body: dict, x_auth_token: str = Header(default=None)):
    return {**body, "id": "user-1", "balance": 0}

@router.get("/users")
async def list_users(x_auth_token: str = Header(default=None)):
    return []

@router.put("/users/{user_id}")
async def update_user(user_id: str, body: dict, x_auth_token: str = Header(default=None)):
    return {**body, "id": user_id}

@router.patch("/users/{user_id}/status")
async def update_user_status(user_id: str, body: dict, x_auth_token: str = Header(default=None)):
    return {"id": user_id, "is_active": body.get("is_active", True)}


# --- Balance ---------------------------------------------------------------- #
@router.post("/balance/add")
async def add_balance(body: dict, x_auth_token: str = Header(default=None)):
    return {"user_id": body.get("user_id"), "balance": 0, "added": 0}

@router.post("/balance/set")
async def set_balance(body: dict, x_auth_token: str = Header(default=None)):
    return {"user_id": body.get("user_id"), "balance": 0}


# --- Boosts & Groups -------------------------------------------------------- #
@router.get("/project-groups")
async def list_project_groups(x_auth_token: str = Header(default=None)):
    return []

@router.get("/boosts")
async def list_boosts(project_id: str = "", x_auth_token: str = Header(default=None)):
    return []
