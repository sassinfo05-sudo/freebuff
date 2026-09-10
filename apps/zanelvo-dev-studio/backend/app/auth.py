"""Single-admin login. No signup, no accounts collection — the credential lives only in the
`ADMIN_PASSWORD` environment variable and is compared in constant time, never stored or logged."""
from __future__ import annotations

import hmac
import time
from collections import defaultdict
from typing import Dict, List

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel

from . import config
from .deps import COOKIE_NAME, require_auth
from .security import create_access_token

router = APIRouter(prefix="/api/auth", tags=["auth"])

# Minimal brute-force guard: this app has exactly one password and may be reachable outside
# localhost, so a naive unlimited-attempt login is a real risk. In-memory is fine — restarting
# the process resetting the counter is an acceptable tradeoff for a single-process personal tool.
_attempts: Dict[str, List[float]] = defaultdict(list)
_MAX_ATTEMPTS = 8
_WINDOW_SECONDS = 300


def _rate_limited(ip: str) -> bool:
    now = time.time()
    _attempts[ip] = [t for t in _attempts[ip] if now - t < _WINDOW_SECONDS]
    return len(_attempts[ip]) >= _MAX_ATTEMPTS


class LoginRequest(BaseModel):
    password: str


@router.post("/login")
async def login(body: LoginRequest, request: Request, response: Response):
    ip = request.client.host if request.client else "unknown"
    if _rate_limited(ip):
        raise HTTPException(status_code=429, detail="Too many attempts. Try again in a few minutes.")
    _attempts[ip].append(time.time())
    if not hmac.compare_digest(body.password, config.ADMIN_PASSWORD):
        raise HTTPException(status_code=401, detail="Incorrect password")
    _attempts[ip] = []
    token = create_access_token()
    response.set_cookie(
        COOKIE_NAME, token, httponly=True, samesite="lax",
        secure=config.is_production(), max_age=config.JWT_ACCESS_TTL_MIN * 60, path="/",
    )
    return {"ok": True}


@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie(COOKIE_NAME, path="/")
    return {"ok": True}


@router.get("/me")
async def me(user: str = Depends(require_auth)):
    return {"authenticated": True}
