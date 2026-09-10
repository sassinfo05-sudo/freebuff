"""Deterministic tests for FileService: path traversal protection and stale-patch protection.
Uses a real temp directory (no Mongo/network needed)."""
import os

import pytest

from app.devstudio.services.file_service import FileService, PathEscapeError, StalePatchError


@pytest.fixture
def fs(tmp_path):
    (tmp_path / "backend").mkdir()
    (tmp_path / "backend" / "app.py").write_text("print('hello')\n")
    return FileService(str(tmp_path))


def test_read_and_list_tree(fs):
    entries = fs.list_tree()
    paths = {e.path for e in entries}
    assert "backend/app.py" in paths
    assert fs.read_file("backend/app.py") == "print('hello')\n"


def test_path_traversal_is_blocked(fs):
    with pytest.raises(PathEscapeError):
        fs.read_file("../../../../etc/passwd")
    with pytest.raises(PathEscapeError):
        fs.create_file("../escape.txt", "x")


def test_absolute_looking_path_is_remapped_inside_the_workspace_not_the_host(fs):
    # A leading "/" is treated as workspace-root-relative (never the real host filesystem root),
    # so this safely 404s instead of ever reaching the real /etc/passwd.
    with pytest.raises(FileNotFoundError):
        fs.read_file("/etc/passwd")


def test_create_file_refuses_to_overwrite_existing(fs):
    fs.create_file("new.txt", "hi")
    with pytest.raises(FileExistsError):
        fs.create_file("new.txt", "again")


def test_patch_file_happy_path(fs):
    h = fs.read_hash("backend/app.py")
    new_hash = fs.patch_file("backend/app.py", "hello", "world", expected_hash=h)
    assert fs.read_file("backend/app.py") == "print('world')\n"
    assert new_hash == fs.read_hash("backend/app.py")


def test_stale_patch_is_rejected(fs, tmp_path):
    stale_hash = fs.read_hash("backend/app.py")
    # Simulate a concurrent writer (another agent / the founder) changing the file after we read it.
    (tmp_path / "backend" / "app.py").write_text("print('someone else changed this')\n")
    with pytest.raises(StalePatchError):
        fs.patch_file("backend/app.py", "hello", "world", expected_hash=stale_hash)


def test_patch_file_requires_unique_match(fs, tmp_path):
    (tmp_path / "backend" / "dup.py").write_text("x = 1\nx = 1\n")
    with pytest.raises(ValueError):
        fs.patch_file("backend/dup.py", "x = 1", "x = 2")  # matches twice, ambiguous


def test_move_and_delete(fs):
    fs.create_file("a.txt", "content")
    fs.move_file("a.txt", "moved/b.txt")
    assert fs.read_file("moved/b.txt") == "content"
    fs.delete_file("moved/b.txt")
    with pytest.raises(FileNotFoundError):
        fs.read_file("moved/b.txt")


def test_search_repo_finds_matches(fs):
    results = fs.search_repo("hello")
    assert any(r["path"] == "backend/app.py" for r in results)
