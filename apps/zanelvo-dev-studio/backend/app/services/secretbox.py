"""Encryption-at-rest for integration secrets (Fernet / AES-128-CBC + HMAC).

Key: `SECRETS_ENC_KEY` env (urlsafe-base64 32 bytes) or, when absent, derived from JWT_SECRET
via SHA-256 so existing deployments encrypt without extra configuration. Values are stored
as `enc:v1:<token>`; plaintext legacy values are transparently read and re-encrypted on the
next save. Never log values.
"""
from __future__ import annotations

import base64
import hashlib
import os
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken

_PREFIX = "enc:v1:"
_fernet: Optional[Fernet] = None


def _key() -> bytes:
    raw = os.environ.get("SECRETS_ENC_KEY", "").strip()
    if raw:
        # Accept a proper Fernet key as-is; otherwise derive a valid 32-byte key from
        # whatever string was provided so a misconfigured value never crashes crypto.
        try:
            Fernet(raw.encode())
            return raw.encode()
        except Exception:  # noqa: BLE001
            return base64.urlsafe_b64encode(hashlib.sha256(("zanelvo-secrets:" + raw).encode()).digest())
    from .. import config
    return base64.urlsafe_b64encode(hashlib.sha256(("zanelvo-secrets:" + config.JWT_SECRET).encode()).digest())


def _f() -> Fernet:
    global _fernet
    if _fernet is None:
        _fernet = Fernet(_key())
    return _fernet


def encrypt(value: str) -> str:
    if value is None or value == "" or str(value).startswith(_PREFIX):
        return value
    return _PREFIX + _f().encrypt(str(value).encode()).decode()


def decrypt(value: str) -> str:
    if not value or not str(value).startswith(_PREFIX):
        return value or ""
    try:
        return _f().decrypt(str(value)[len(_PREFIX):].encode()).decode()
    except (InvalidToken, Exception):  # noqa: BLE001
        return ""


def is_encrypted(value: str) -> bool:
    return bool(value) and str(value).startswith(_PREFIX)
