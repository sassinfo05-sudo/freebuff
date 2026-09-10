"""Deterministic tests for DiffService's unified-diff parser. Pure string parsing, no git/DB."""
from app.devstudio.services.diff_service import parse_unified_diff

_SAMPLE_DIFF = """\
diff --git a/backend/app/foo.py b/backend/app/foo.py
index e69de29..8c7e5a1 100644
--- a/backend/app/foo.py
+++ b/backend/app/foo.py
@@ -1,3 +1,4 @@
 def foo():
-    return 1
+    return 2
+    # extra line

diff --git a/backend/app/new_file.py b/backend/app/new_file.py
new file mode 100644
index 0000000..e69de29
--- /dev/null
+++ b/backend/app/new_file.py
@@ -0,0 +1,2 @@
+def bar():
+    pass
diff --git a/backend/app/old_file.py b/backend/app/old_file.py
deleted file mode 100644
index e69de29..0000000
--- a/backend/app/old_file.py
+++ /dev/null
@@ -1,1 +0,0 @@
-def gone():
"""


def test_parses_all_three_files():
    summary = parse_unified_diff(_SAMPLE_DIFF)
    paths = {f.path: f for f in summary.files}
    assert set(paths) == {"backend/app/foo.py", "backend/app/new_file.py", "backend/app/old_file.py"}


def test_change_types():
    summary = parse_unified_diff(_SAMPLE_DIFF)
    by_path = {f.path: f for f in summary.files}
    assert by_path["backend/app/foo.py"].change_type == "modified"
    assert by_path["backend/app/new_file.py"].change_type == "added"
    assert by_path["backend/app/old_file.py"].change_type == "deleted"


def test_line_counts():
    summary = parse_unified_diff(_SAMPLE_DIFF)
    by_path = {f.path: f for f in summary.files}
    assert by_path["backend/app/foo.py"].additions == 2
    assert by_path["backend/app/foo.py"].deletions == 1
    assert by_path["backend/app/new_file.py"].additions == 2
    assert by_path["backend/app/old_file.py"].deletions == 1
    assert summary.total_additions == 4
    assert summary.total_deletions == 2


def test_empty_diff_is_no_changes():
    summary = parse_unified_diff("")
    assert summary.files == []
    assert summary.total_additions == 0
    assert summary.total_deletions == 0


def test_to_dict_shape():
    summary = parse_unified_diff(_SAMPLE_DIFF)
    d = summary.to_dict()
    assert d["changed_file_count"] == 3
    assert d["total_additions"] == 4
    assert d["total_deletions"] == 2
    assert isinstance(d["files"], list)
