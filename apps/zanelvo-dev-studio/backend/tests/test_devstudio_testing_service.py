"""Regression tests for TestingService, specifically the cwd/command separation.

Caught by live end-to-end testing (not just unit tests): TestingService used to bake `cd <dir> &&`
into command strings. That fails two different ways — CommandPolicy rejects it (`cd` isn't on the
allowlist) and, even if it were, ExecutionService runs commands via `create_subprocess_exec`, which
never invokes a shell and can't interpret `&&` at all. `cwd` must always be a separate field.
"""
import json
import os

from app.devstudio.services import command_policy, testing_service


def _write(path, content=""):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as fh:
        fh.write(content)


def test_flat_repo_layout_backend_and_frontend_at_root(tmp_path):
    _write(tmp_path / "backend" / "requirements.txt")
    _write(tmp_path / "backend" / "pytest.ini")
    _write(tmp_path / "backend" / "ruff.toml")
    _write(tmp_path / "frontend" / "package.json", json.dumps({"scripts": {"test": "x", "build": "x"}}))

    profile = testing_service.discover(str(tmp_path))
    assert profile.has_backend and profile.backend_dir == "backend"
    assert profile.has_frontend and profile.frontend_dir == "frontend"


def test_nested_monorepo_layout_is_discovered(tmp_path):
    _write(tmp_path / "apps" / "myapp" / "backend" / "requirements.txt")
    _write(tmp_path / "apps" / "myapp" / "frontend" / "package.json",
           json.dumps({"scripts": {"build": "x"}}))

    profile = testing_service.discover(str(tmp_path))
    assert profile.has_backend and profile.backend_dir == "apps/myapp/backend"
    assert profile.has_frontend and profile.frontend_dir == "apps/myapp/frontend"


def test_selected_commands_never_contain_cd_or_shell_operators(tmp_path):
    _write(tmp_path / "apps" / "myapp" / "backend" / "requirements.txt")
    _write(tmp_path / "apps" / "myapp" / "backend" / "ruff.toml")
    _write(tmp_path / "apps" / "myapp" / "frontend" / "package.json",
           json.dumps({"scripts": {"test": "x", "build": "x", "lint": "x"}}))

    profile = testing_service.discover(str(tmp_path))
    commands = testing_service.select_commands(profile, changed_files=[])
    assert commands, "expected at least one command to be selected"
    for c in commands:
        assert "cd " not in c["command"]
        assert "&&" not in c["command"]
        assert ";" not in c["command"]


def test_every_selected_command_passes_command_policy(tmp_path):
    _write(tmp_path / "backend" / "requirements.txt")
    _write(tmp_path / "backend" / "ruff.toml")
    _write(tmp_path / "frontend" / "package.json",
           json.dumps({"scripts": {"test": "x", "build": "x", "lint": "x"}}))

    profile = testing_service.discover(str(tmp_path))
    commands = testing_service.select_commands(profile, changed_files=[])
    for c in commands:
        decision = command_policy.evaluate(c["command"])
        assert decision.allowed, f"{c['command']!r} should be allowed: {decision.reason}"


def test_cwd_is_reported_separately_from_command(tmp_path):
    _write(tmp_path / "apps" / "myapp" / "backend" / "requirements.txt")

    profile = testing_service.discover(str(tmp_path))
    commands = testing_service.select_commands(profile, changed_files=[])
    backend_cmd = next(c for c in commands if c["type"] == "backend_unit")
    assert backend_cmd["command"] == "python -m pytest -q"
    assert backend_cmd["cwd"] == "apps/myapp/backend"
