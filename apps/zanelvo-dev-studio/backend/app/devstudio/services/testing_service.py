"""TestingService — discovers what test/build/lint commands a repository actually supports,
and picks a risk-appropriate subset based on which files changed (never "always run everything").
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Dict, List

_ROUTE_HINTS = {
    "auth": ["auth", "login", "session", "jwt", "permission", "role"],
    "payment": ["stripe", "payment", "billing", "webhook", "checkout", "invoice"],
    "frontend": ["frontend/src", ".jsx", ".tsx", "frontend/"],
    "backend": ["backend/app", ".py"],
}


@dataclass
class TestingProfile:
    has_frontend: bool = False
    has_backend: bool = False
    frontend_test_cmd: str = None
    frontend_build_cmd: str = None
    frontend_lint_cmd: str = None
    backend_test_cmd: str = None
    backend_lint_cmd: str = None
    playwright_config: bool = False

    def to_dict(self) -> dict:
        return self.__dict__


def discover(workspace_path: str) -> TestingProfile:
    profile = TestingProfile()
    fe_pkg = os.path.join(workspace_path, "frontend", "package.json")
    root_pkg = os.path.join(workspace_path, "package.json")
    pkg_path = fe_pkg if os.path.isfile(fe_pkg) else (root_pkg if os.path.isfile(root_pkg) else None)
    if pkg_path:
        profile.has_frontend = True
        try:
            with open(pkg_path) as fh:
                pkg = json.load(fh)
            scripts = pkg.get("scripts", {})
            prefix = "cd frontend && " if pkg_path == fe_pkg else ""
            if "test" in scripts:
                profile.frontend_test_cmd = f"{prefix}npm test"
            if "build" in scripts:
                profile.frontend_build_cmd = f"{prefix}npm run build"
            if "lint" in scripts:
                profile.frontend_lint_cmd = f"{prefix}npm run lint"
        except (OSError, json.JSONDecodeError):
            pass

    backend_dir = os.path.join(workspace_path, "backend")
    has_pytest_ini = os.path.isfile(os.path.join(backend_dir, "pytest.ini")) or \
        os.path.isfile(os.path.join(workspace_path, "pytest.ini"))
    has_requirements = os.path.isfile(os.path.join(backend_dir, "requirements.txt")) or \
        os.path.isfile(os.path.join(workspace_path, "requirements.txt"))
    if has_pytest_ini or has_requirements or os.path.isdir(os.path.join(backend_dir, "tests")):
        profile.has_backend = True
        profile.backend_test_cmd = "cd backend && python -m pytest -q" if os.path.isdir(backend_dir) \
            else "python -m pytest -q"
        ruff_cfg = os.path.join(backend_dir, "ruff.toml")
        if os.path.isfile(ruff_cfg):
            profile.backend_lint_cmd = "cd backend && python -m ruff check ."

    for cfg in ("playwright.config.ts", "playwright.config.js", "frontend/playwright.config.ts"):
        if os.path.isfile(os.path.join(workspace_path, cfg)):
            profile.playwright_config = True
            break

    return profile


def classify_subsystems(changed_files: List[str]) -> List[str]:
    hits = set()
    joined = "\n".join(changed_files).lower()
    for subsystem, hints in _ROUTE_HINTS.items():
        if any(h in joined for h in hints):
            hits.add(subsystem)
    return sorted(hits)


def select_commands(profile: TestingProfile, changed_files: List[str]) -> List[Dict[str, str]]:
    """Risk-based selection: pick the narrowest set of real commands relevant to what changed."""
    subsystems = classify_subsystems(changed_files)
    commands: List[Dict[str, str]] = []
    touches_frontend = "frontend" in subsystems or not changed_files
    touches_backend = "backend" in subsystems or not changed_files
    large_refactor = len(changed_files) > 25

    if (touches_backend or large_refactor) and profile.backend_test_cmd:
        commands.append({"type": "backend_unit", "command": profile.backend_test_cmd})
    if (touches_backend or large_refactor) and profile.backend_lint_cmd:
        commands.append({"type": "lint", "command": profile.backend_lint_cmd})
    if (touches_frontend or large_refactor) and profile.frontend_test_cmd:
        commands.append({"type": "frontend_unit", "command": profile.frontend_test_cmd})
    if (touches_frontend or large_refactor) and profile.frontend_build_cmd:
        commands.append({"type": "build", "command": profile.frontend_build_cmd})
    if (touches_frontend or large_refactor) and profile.frontend_lint_cmd:
        commands.append({"type": "lint", "command": profile.frontend_lint_cmd})
    return commands
