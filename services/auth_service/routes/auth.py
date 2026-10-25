"""Auth service routes — login, register, token refresh, email verification."""

from datetime import datetime, timedelta, timezone
from uuid import UUID

import bcrypt
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database.session import get_session
from shared.config import settings
from shared.ratelimit import login_limiter
from shared.validation import validate_password
from services.auth_service.domain.models import User
from services.auth_service.domain.schemas import (
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    RefreshRequest,
)
from shared.email.sender import send_verification_email

router = APIRouter(tags=["auth"])

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        # bcrypt rejects secrets longer than 72 bytes — treat as a failed match, not a 500.
        return False


def _create_access_token(subject_id: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_minutes)
    return jwt.encode(
        {"sub": subject_id, "exp": expire, "type": "access"},
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )


def _create_refresh_token(subject_id: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_days)
    return jwt.encode(
        {"sub": subject_id, "exp": expire, "type": "refresh"},
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )


def _create_verify_token(subject_id: str) -> str:
    """Single-purpose token for the e-mail verification link — NOT a session token."""
    expire = datetime.now(timezone.utc) + timedelta(hours=24)
    return jwt.encode(
        {"sub": subject_id, "exp": expire, "type": "verify"},
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )


def _set_auth_cookies(response: Response, access_token: str, refresh_token: str) -> None:
    """Set the httpOnly auth cookies; Secure is driven by settings so prod can require HTTPS."""
    response.set_cookie(
        key="token", value=access_token, httponly=True, secure=settings.cookie_secure,
        samesite="lax", max_age=settings.access_token_minutes * 60,
    )
    response.set_cookie(
        key="refresh_token", value=refresh_token, httponly=True, secure=settings.cookie_secure,
        samesite="lax", max_age=settings.refresh_token_days * 86400,
    )


@router.post("/register")
async def register(
    body: RegisterRequest,
    response: Response,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
):
    """Register a new user and return JWT tokens."""
    validate_password(body.password)
    existing = await session.execute(
        select(User).where(User.email == body.email)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Email already registered")

    user = User(
        email=body.email,
        password_hash=_hash_password(body.password),
        display_name=body.display_name,
        is_verified=False,  # requires email verification
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)

    # Send verification email (non-blocking). A single-purpose token, not a login session.
    verify_token = _create_verify_token(str(user.id))
    verify_url = f"{settings.frontend_url or 'http://localhost:5173'}/verify-email?token={verify_token}"
    background_tasks.add_task(send_verification_email, body.email, verify_url)

    access_token = _create_access_token(str(user.id))
    refresh_token = _create_refresh_token(str(user.id))

    _set_auth_cookies(response, access_token, refresh_token)
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
    )


@router.post("/login")
async def login(body: LoginRequest, request: Request, response: Response, session: AsyncSession = Depends(get_session)):
    """Authenticate user and return JWT tokens. Throttled per IP + e-mail after repeated failures."""
    client_ip = request.client.host if request.client else "unknown"
    rl_key = f"{client_ip}:{(body.email or '').strip().lower()}"
    if login_limiter.is_blocked(rl_key):
        raise HTTPException(status_code=429, detail="Too many login attempts. Try again later.")

    result = await session.execute(
        select(User).where(User.email == body.email)
    )
    user = result.scalar_one_or_none()

    if not user or not _verify_password(body.password, user.password_hash):
        login_limiter.record(rl_key)
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not user.is_active:
        raise HTTPException(status_code=401, detail="Account is disabled")

    login_limiter.clear(rl_key)
    access_token = _create_access_token(str(user.id))
    refresh_token = _create_refresh_token(str(user.id))

    _set_auth_cookies(response, access_token, refresh_token)
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
    )


@router.post("/refresh")
async def refresh(body: RefreshRequest, response: Response, session: AsyncSession = Depends(get_session)):
    """Refresh access token using a valid refresh token."""
    try:
        payload = jwt.decode(
            body.refresh_token, settings.jwt_secret, algorithms=[settings.jwt_algorithm]
        )
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid token type")
        user_id = UUID(payload["sub"])
    except (JWTError, KeyError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")

    access_token = _create_access_token(str(user.id))
    refresh_token = _create_refresh_token(str(user.id))

    _set_auth_cookies(response, access_token, refresh_token)
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
    )


@router.post("/verify-email")
async def verify_email(token: str = Depends(oauth2_scheme), session: AsyncSession = Depends(get_session)):
    """Verify user email using the single-purpose verification token from the e-mail link."""
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        if payload.get("type") != "verify":
            raise HTTPException(status_code=401, detail="Invalid token type")
        user_id = UUID(payload["sub"])
    except (JWTError, KeyError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.is_verified:
        return {"message": "Email already verified"}

    user.is_verified = True
    await session.commit()

    return {"message": "Email verified successfully"}


@router.get("/me")
async def get_me(token: str = Depends(oauth2_scheme)):
    """Get current user profile from JWT token."""
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        return {"user_id": payload["sub"], "token_type": payload.get("type")}
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
