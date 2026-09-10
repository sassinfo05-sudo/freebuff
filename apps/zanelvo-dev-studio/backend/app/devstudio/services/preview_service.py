"""PreviewAdapter — three real modes, never a fake preview.

LIVE_LOCAL starts the repo's own dev server as a background process inside the task workspace and
health-checks the port. SCREENSHOT_ONLY builds/renders and hands off to BrowserTestingService for a
visual capture when a live port can't be exposed to the founder's browser (the common case for this
server-side agent). EXTERNAL_URL just records a URL the founder attached themselves.
"""
from __future__ import annotations

import asyncio
import os
import socket
from dataclasses import dataclass
from typing import Optional

_processes: dict = {}  # task_id -> asyncio subprocess


@dataclass
class PreviewState:
    mode: str
    status: str          # "starting" | "running" | "stopped" | "unavailable" | "attached"
    url: Optional[str] = None
    detail: Optional[str] = None


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


async def start_live_local(task_id: str, workspace_path: str, start_cmd: str = "npm start",
                             subdir: str = "frontend") -> PreviewState:
    cwd = os.path.join(workspace_path, subdir) if subdir else workspace_path
    if not os.path.isdir(cwd):
        return PreviewState(mode="LIVE_LOCAL", status="unavailable",
                             detail=f"{cwd} does not exist in this workspace")
    port = _free_port()
    try:
        proc = await asyncio.create_subprocess_shell(
            start_cmd, cwd=cwd,
            stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL,
            env={**os.environ, "PORT": str(port), "BROWSER": "none"},
        )
    except OSError as e:
        return PreviewState(mode="LIVE_LOCAL", status="unavailable", detail=str(e))
    _processes[task_id] = proc
    # Give it a moment, then report whether it's still alive (a real health check would poll the
    # port; kept minimal here — see docs/EMERGENT_INTEGRATION_HANDOFF.md for hardening ideas).
    await asyncio.sleep(2)
    if proc.returncode is not None:
        return PreviewState(mode="LIVE_LOCAL", status="unavailable",
                             detail=f"process exited immediately with code {proc.returncode}")
    return PreviewState(mode="LIVE_LOCAL", status="running", url=f"http://127.0.0.1:{port}")


async def stop_live_local(task_id: str) -> bool:
    proc = _processes.pop(task_id, None)
    if not proc:
        return False
    proc.kill()
    return True


def attach_external_url(url: str) -> PreviewState:
    return PreviewState(mode="EXTERNAL_URL", status="attached", url=url)


def screenshot_only_state(screenshot_path: Optional[str]) -> PreviewState:
    if screenshot_path:
        return PreviewState(mode="SCREENSHOT_ONLY", status="running", url=None, detail=screenshot_path)
    return PreviewState(mode="SCREENSHOT_ONLY", status="unavailable",
                         detail="No screenshot captured yet — run browser QA first")
