"""JWT issuance/verification for the single admin session. No passwords are stored anywhere —
`ADMIN_PASSWORD` (config.py, from env) is compared directly at login; nothing here persists it."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict

import jwt

from . import config


def create_access_token() -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": "admin",
        "iat": int(now.timestamp()),
        "exp": now + timedelta(minutes=config.JWT_ACCESS_TTL_MIN),
    }
    return jwt.encode(payload, config.JWT_SECRET, algorithm=config.JWT_ALG)


def decode_access_token(token: str) -> Dict[str, Any]:
    return jwt.decode(token, config.JWT_SECRET, algorithms=[config.JWT_ALG])
