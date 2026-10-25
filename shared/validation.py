"""Small request-body checks for routes that accept a plain ``dict`` body."""

from urllib.parse import urlsplit
from uuid import UUID

from fastapi import HTTPException

# bcrypt hashes at most the first 72 bytes; longer inputs raise instead of silently truncating.
MAX_PASSWORD_BYTES = 72
MIN_PASSWORD_LEN = 6
# Only these URL schemes may be stored and later rendered into href/src attributes.
_SAFE_URL_SCHEMES = frozenset({"http", "https", ""})


def require_fields(body: dict, *names: str) -> None:
    """Reject the request with 422 if any of ``names`` is missing or empty in ``body``."""
    missing = [n for n in names if body.get(n) in (None, "")]
    if missing:
        raise HTTPException(status_code=422, detail=f"Required field(s): {', '.join(missing)}")


def parse_uuid(value: object, field: str) -> UUID:
    """Parse a UUID from request input, or reject with 422."""
    try:
        return value if isinstance(value, UUID) else UUID(str(value))
    except ValueError:
        raise HTTPException(status_code=422, detail=f"Invalid {field}")


def validate_password(password: str) -> str:
    """Reject passwords that are too short or longer than bcrypt can hash (422)."""
    if not isinstance(password, str) or len(password) < MIN_PASSWORD_LEN:
        raise HTTPException(status_code=422, detail=f"Password must be at least {MIN_PASSWORD_LEN} characters")
    if len(password.encode("utf-8")) > MAX_PASSWORD_BYTES:
        raise HTTPException(status_code=422, detail=f"Password must be at most {MAX_PASSWORD_BYTES} bytes")
    return password


def is_unsafe_url(value: object) -> bool:
    """True if ``value`` has a scheme other than http/https (so unsafe to render into href/src)."""
    if value in (None, ""):
        return False
    return urlsplit(str(value)).scheme.lower() not in _SAFE_URL_SCHEMES


def ensure_safe_url(value: object, field: str = "url") -> None:
    """Reject non-http(s) URLs (e.g. ``javascript:``/``data:``) that could run when rendered (422)."""
    if is_unsafe_url(value):
        raise HTTPException(status_code=422, detail=f"{field} must be an http(s) URL")


def csv_safe(value: object) -> str:
    """Neutralise spreadsheet formula injection: a leading =,+,-,@ is prefixed with an apostrophe."""
    text = "" if value is None else str(value)
    if text and text[0] in ("=", "+", "-", "@"):
        return "'" + text
    return text
