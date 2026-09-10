"""Deterministic tests for ExecutionService's cwd resolution and safety, and CommandBlocked
enforcement. No DB/network — exercises the pure/sync helpers directly."""
import pytest

from app.devstudio.services.execution_service import CommandBlocked, _resolve_cwd


def test_resolve_cwd_defaults_to_workspace_root(tmp_path):
    assert _resolve_cwd(str(tmp_path), None) == str(tmp_path.resolve())
    assert _resolve_cwd(str(tmp_path), "") == str(tmp_path.resolve())


def test_resolve_cwd_joins_a_real_subdir(tmp_path):
    (tmp_path / "backend").mkdir()
    assert _resolve_cwd(str(tmp_path), "backend") == str((tmp_path / "backend").resolve())


def test_resolve_cwd_rejects_escaping_subdir(tmp_path):
    with pytest.raises(CommandBlocked):
        _resolve_cwd(str(tmp_path), "../../../../etc")
