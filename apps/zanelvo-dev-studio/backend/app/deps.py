"""Auth dependency for the single-admin session. Every non-login route requires a valid session
cookie — there is no per-role gating (there's only one user), unlike the Saas app this was ported
from."""
from __future__ import annotations

import jwt
from fastapi import HTTPException, Request, status

from .security import decode_access_token

COOKIE_NAME = "zds_token"


def _token_from_request(request: Request) -> str:
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[len("Bearer "):].strip()
    tok = request.cookies.get(COOKIE_NAME)
    if tok:
        return tok
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")


async def require_auth(request: Request) -> str:
    """Returns the fixed admin identity string on success. Raises 401 otherwise."""
    token = _token_from_request(request)
    try:
        payload = decode_access_token(token)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Session expired — please sign in again")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid session")
    if payload.get("sub") != "admin":
        raise HTTPException(status_code=401, detail="Invalid session")
    return "admin"
