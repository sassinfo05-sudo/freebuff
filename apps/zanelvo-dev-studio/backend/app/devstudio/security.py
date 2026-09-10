"""Access control for Dev Studio. This standalone app has exactly one user (the founder running
it), so both names below resolve to the same underlying check — kept as two names for parity with
how a multi-role deployment would gate read vs. write actions, and so routes.py reads clearly."""
from __future__ import annotations

from fastapi import Depends

from ..deps import require_auth

require_devstudio_access = require_auth
require_devstudio_write = require_auth


async def current_staff_id(user: str = Depends(require_devstudio_access)) -> str:
    return user
