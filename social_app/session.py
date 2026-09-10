"""In-process session state for the social platform (FP-003).

Sessions are random tokens mapped to user ids in a process-local dictionary:
logging in establishes a session, the ``session`` cookie carries the token,
and a process restart drops every session. The mapping is lock-protected so
``ThreadingHTTPServer`` can serve concurrent requests safely.

Public contract (task card §3.3): ``create_session`` / ``get_user_id`` /
``destroy_session`` / ``current_user_id`` / ``require_login`` plus the two
cookie-header helpers. ``require_login`` delegates to the FP-001 web layer's
``social_app.app.redirect`` when available, shown as the login guard for
protected pages.
"""

import secrets
import threading
from dataclasses import dataclass, field

SESSION_COOKIE = "session"
LOGIN_PATH = "/login"
REDIRECT_STATUS = 303

_sessions: dict[str, int] = {}
_lock = threading.Lock()


@dataclass
class _FallbackResponse:
    """Minimal ``Response`` shape used until the FP-001 web layer exists."""

    status: int = 200
    body: str = ""
    content_type: str = "text/html; charset=utf-8"
    headers: dict[str, str] = field(default_factory=dict)


def _fallback_redirect(
    location: str, status: int = REDIRECT_STATUS
) -> _FallbackResponse:
    return _FallbackResponse(status=status, headers={"Location": location})


def redirect(location: str, status: int = REDIRECT_STATUS):
    """Build a redirect response via ``social_app.app.redirect`` if present.

    The import is resolved per call so this module stays usable before FP-001
    (card §6 Mock strategy): the fallback keeps the public signature and the
    returned object's ``status`` / ``headers`` contract intact.
    """
    try:
        from social_app.app import redirect as app_redirect
    except ImportError:
        return _fallback_redirect(location, status=status)
    return app_redirect(location, status=status)


def create_session(user_id: int) -> str:
    """Create a session for ``user_id`` and return its random token."""
    token = secrets.token_urlsafe(32)
    with _lock:
        _sessions[token] = user_id
    return token


def get_user_id(token: str | None) -> int | None:
    """Return the user id for ``token``, or ``None`` if unknown/absent."""
    if not token:
        return None
    with _lock:
        return _sessions.get(token)


def destroy_session(token: str | None) -> None:
    """Invalidate ``token``. Missing/unknown tokens are silently ignored."""
    if not token:
        return
    with _lock:
        _sessions.pop(token, None)


def current_user_id(request) -> int | None:
    """Return the logged-in user id for ``request`` (None when anonymous)."""
    cookies = getattr(request, "cookies", None) or {}
    return get_user_id(cookies.get(SESSION_COOKIE))


def require_login(request):
    """Return ``None`` when logged in, otherwise a 303 redirect to /login."""
    if current_user_id(request) is not None:
        return None
    return redirect(LOGIN_PATH)


def cookie_header(token: str) -> str:
    """``Set-Cookie`` value that stores ``token`` as the session cookie."""
    return f"{SESSION_COOKIE}={token}; HttpOnly; Path=/"


def clear_cookie_header() -> str:
    """``Set-Cookie`` value that expires the session cookie."""
    return f"{SESSION_COOKIE}=; HttpOnly; Path=/; Max-Age=0"
