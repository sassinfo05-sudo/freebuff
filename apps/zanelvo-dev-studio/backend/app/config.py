"""Central config for the standalone Zanelvo Dev Studio app. This app has exactly one user (the
founder running it) — there is no signup, no roles, no billing. See CLAUDE.md."""
import os

APP_ENV = os.environ.get("APP_ENV", "dev").strip().lower()

# Required. No default — a missing secret must fail loudly at boot, not silently sign requests
# with a guessable value.
JWT_SECRET = os.environ["JWT_SECRET"]
JWT_ALG = "HS256"
JWT_ACCESS_TTL_MIN = int(os.environ.get("JWT_ACCESS_TTL_MIN", "10080"))  # 7 days — single-user tool

# The one admin credential. Required — there is no account system to fall back on.
ADMIN_PASSWORD = os.environ["ADMIN_PASSWORD"]

CORS_ORIGINS = [o.strip() for o in os.environ.get("CORS_ORIGINS", "http://localhost:5173").split(",")
                 if o.strip()]


def is_production() -> bool:
    return APP_ENV not in ("dev", "test")
