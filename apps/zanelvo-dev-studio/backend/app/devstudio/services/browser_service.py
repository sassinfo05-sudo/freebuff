"""BrowserTestingService — real Playwright automation, gracefully degraded when the optional
`playwright` package (backend/requirements-devstudio.txt) isn't installed in this environment.
A degraded run is recorded as BrowserRun.status="unavailable" with a clear reason, never faked.
"""
from __future__ import annotations

import os
import uuid
from typing import List, Optional

from ...db import get_db
from ..models import BrowserRun, Screenshot

_SCREENSHOT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
                                "var", "devstudio", "screenshots")


def _playwright():
    try:
        from playwright.async_api import async_playwright
        return async_playwright
    except ImportError:
        return None


async def run_scenario(task_id: str, base_url: str, scenario: str, actions: Optional[List[dict]] = None,
                        viewport: str = "1280x800") -> BrowserRun:
    """`actions` is a list of {type: "goto"|"click"|"fill", selector?, value?, path?}. Kept simple
    and declarative so the QA agent's structured output can drive it directly."""
    async_playwright = _playwright()
    db = get_db()
    if async_playwright is None:
        run = BrowserRun(task_id=task_id, scenario=scenario, status="unavailable",
                          notes="playwright is not installed. Install backend/requirements-devstudio.txt "
                                "to enable real browser QA.")
        res = await db.ds_browser_runs.insert_one(run.to_mongo())
        run.id = str(res.inserted_id)
        return run

    w, h = (int(x) for x in viewport.split("x"))
    console_errors: List[str] = []
    failed_requests: List[str] = []
    run = BrowserRun(task_id=task_id, scenario=scenario, status="running")
    res = await db.ds_browser_runs.insert_one(run.to_mongo())
    run.id = str(res.inserted_id)

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page(viewport={"width": w, "height": h})
            page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
            page.on("requestfailed", lambda req: failed_requests.append(f"{req.method} {req.url}"))
            await page.goto(base_url, wait_until="domcontentloaded", timeout=20000)
            for action in (actions or []):
                atype = action.get("type")
                if atype == "goto":
                    await page.goto(action["value"], wait_until="domcontentloaded", timeout=20000)
                elif atype == "click":
                    await page.click(action["selector"], timeout=10000)
                elif atype == "fill":
                    await page.fill(action["selector"], action.get("value", ""), timeout=10000)
                elif atype == "wait":
                    await page.wait_for_timeout(int(action.get("value", 500)))
            os.makedirs(_SCREENSHOT_DIR, exist_ok=True)
            shot_path = os.path.join(_SCREENSHOT_DIR, f"{task_id}-{uuid.uuid4().hex[:8]}.png")
            await page.screenshot(path=shot_path, full_page=True)
            await browser.close()
        status = "failed" if (console_errors or failed_requests) else "passed"
        await db.ds_screenshots.insert_one(Screenshot(
            task_id=task_id, browser_run_id=run.id, label=scenario, path=shot_path,
            viewport=viewport,
        ).to_mongo())
    except Exception as e:  # noqa: BLE001 — a real browser/navigation failure, recorded not swallowed
        status = "failed"
        console_errors.append(f"{type(e).__name__}: {e}")

    await db.ds_browser_runs.update_one({"_id": __oid(run.id)}, {"$set": {
        "status": status, "console_errors": console_errors, "failed_requests": failed_requests,
    }})
    run.status = status
    run.console_errors = console_errors
    run.failed_requests = failed_requests
    return run


def __oid(id_str: str):
    from bson import ObjectId
    return ObjectId(id_str)


async def list_screenshots(task_id: str) -> List[Screenshot]:
    docs = get_db().ds_screenshots.find({"task_id": task_id}).sort("created_at", -1)
    return [Screenshot.from_mongo(d) async for d in docs]
