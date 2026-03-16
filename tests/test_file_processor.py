"""Tests for file_processor module."""
import os
from pathlib import Path

import pytest

from dsviewer import file_processor as fp


FIXTURES = Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------------------
# list_files
# ---------------------------------------------------------------------------

def test_list_files_returns_files_and_dirs(tmp_path):
    (tmp_path / "a.py").write_text("hello")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "b.js").write_text("world")

    results = fp.list_files(str(tmp_path))
    paths = [r["path"] for r in results]
    types = {r["path"]: r["type"] for r in results}

    assert any("a.py" in p for p in paths)
    assert any("b.js" in p for p in paths)
    assert any("sub" in p for p in paths)
    sub_dir = next(p for p in paths if "sub" in p and not p.endswith(".js"))
    assert types[sub_dir] == "directory"


def test_list_files_excludes_node_modules(tmp_path):
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "dep.js").write_text("dep")
    (tmp_path / "src.js").write_text("source")

    results = fp.list_files(str(tmp_path))
    paths = [r["path"] for r in results]
    assert not any("node_modules" in p for p in paths)
    assert any("src.js" in p for p in paths)


def test_list_files_excludes_all_excluded_dirs(tmp_path):
    excluded = [".git", ".svn", "vendor", ".idea", ".vscode",
                "cache", "tmp", "temp", "logs", "dist", "build", "target"]
    for d in excluded:
        (tmp_path / d).mkdir()
        (tmp_path / d / "file.txt").write_text("x")

    results = fp.list_files(str(tmp_path))
    paths = [r["path"] for r in results]
    for d in excluded:
        assert not any(d in p for p in paths), f"Should exclude {d}"


def test_list_files_nonexistent_returns_empty():
    assert fp.list_files("/nonexistent/path/xyz") == []


def test_list_files_self_first_order(tmp_path):
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "file.txt").write_text("x")

    results = fp.list_files(str(tmp_path))
    paths = [r["path"] for r in results]
    sub_idx = next(i for i, r in enumerate(results) if "sub" in r["path"] and r["type"] == "directory")
    file_idx = next(i for i, r in enumerate(results) if "file.txt" in r["path"])
    assert sub_idx < file_idx


# ---------------------------------------------------------------------------
# get_file_content / save_file_content
# ---------------------------------------------------------------------------

def test_read_write_roundtrip(tmp_path):
    f = tmp_path / "test.py"
    fp.save_file_content(str(f), "print('hello')")
    assert fp.get_file_content(str(f)) == "print('hello')"


def test_read_nonexistent_returns_empty():
    assert fp.get_file_content("/nonexistent/file.txt") == ""


def test_save_creates_file(tmp_path):
    f = tmp_path / "new.txt"
    fp.save_file_content(str(f), "content")
    assert f.exists()
    assert f.read_text() == "content"


# ---------------------------------------------------------------------------
# search_in_files
# ---------------------------------------------------------------------------

def test_search_literal(tmp_path):
    f = tmp_path / "f.py"
    f.write_text("# TODO: fix this\nprint('hello')\n# TODO: again\n")
    result = fp.search_in_files([str(f)], "TODO", {"case_sensitive": True, "regex": False})
    assert result["summary"]["total_matches"] == 2
    assert result["summary"]["matched_files"] == 1
    assert len(result["matches"][0]["lines"]) == 2


def test_search_case_insensitive(tmp_path):
    f = tmp_path / "f.txt"
    f.write_text("Hello HELLO hello\n")
    result = fp.search_in_files([str(f)], "hello", {"case_sensitive": False, "regex": False})
    assert result["summary"]["total_matches"] == 3


def test_search_case_sensitive(tmp_path):
    f = tmp_path / "f.txt"
    f.write_text("Hello HELLO hello\n")
    result = fp.search_in_files([str(f)], "hello", {"case_sensitive": True, "regex": False})
    assert result["summary"]["total_matches"] == 1


def test_search_regex(tmp_path):
    f = tmp_path / "f.py"
    f.write_text("foo123\nbar456\nfoo789\n")
    result = fp.search_in_files([str(f)], r"foo\d+", {"case_sensitive": True, "regex": True})
    assert result["summary"]["total_matches"] == 2


def test_search_no_match(tmp_path):
    f = tmp_path / "f.txt"
    f.write_text("nothing here\n")
    result = fp.search_in_files([str(f)], "NOTFOUND", {"case_sensitive": True, "regex": False})
    assert result["summary"]["total_matches"] == 0
    assert result["summary"]["matched_files"] == 0


def test_search_preview_truncated(tmp_path):
    f = tmp_path / "f.txt"
    long_line = "x" * 200 + " NEEDLE " + "y" * 200
    f.write_text(long_line + "\n")
    result = fp.search_in_files([str(f)], "NEEDLE", {"case_sensitive": True, "regex": False})
    preview = result["matches"][0]["lines"][0]["preview"]
    assert len(preview) <= 142  # 140 chars + ellipsis


def test_search_returns_character_indices(tmp_path):
    f = tmp_path / "f.txt"
    f.write_text("abc FIND xyz FIND end\n")
    result = fp.search_in_files([str(f)], "FIND", {"case_sensitive": True, "regex": False})
    indices = result["matches"][0]["lines"][0]["indices"]
    assert 4 in indices
    assert 13 in indices


# ---------------------------------------------------------------------------
# replace_in_files
# ---------------------------------------------------------------------------

def test_replace_literal(tmp_path):
    f = tmp_path / "f.txt"
    f.write_text("foo bar foo\n")
    result = fp.replace_in_files([str(f)], "foo", "baz", {"case_sensitive": True, "regex": False, "dry_run": False})
    assert f.read_text() == "baz bar baz\n"
    assert result["summary"]["total_replaced"] == 2


def test_replace_dry_run(tmp_path):
    f = tmp_path / "f.txt"
    original = "foo bar foo\n"
    f.write_text(original)
    result = fp.replace_in_files([str(f)], "foo", "baz", {"case_sensitive": True, "regex": False, "dry_run": True})
    # File unchanged
    assert f.read_text() == original
    assert result["summary"]["changed_files"] == 1
    assert result["summary"]["dry_run"] is True


def test_replace_regex(tmp_path):
    f = tmp_path / "f.py"
    f.write_text("v1.2.3\nv2.0.0\n")
    result = fp.replace_in_files([str(f)], r"v\d+\.\d+\.\d+", "vX.Y.Z",
                                  {"case_sensitive": True, "regex": True, "dry_run": False})
    assert f.read_text() == "vX.Y.Z\nvX.Y.Z\n"
    assert result["summary"]["total_replaced"] == 2


def test_replace_case_insensitive(tmp_path):
    f = tmp_path / "f.txt"
    f.write_text("Hello HELLO hello\n")
    result = fp.replace_in_files([str(f)], "hello", "hi",
                                  {"case_sensitive": False, "regex": False, "dry_run": False})
    assert result["summary"]["total_replaced"] == 3


def test_replace_invalid_regex_raises(tmp_path):
    f = tmp_path / "f.txt"
    f.write_text("content\n")
    with pytest.raises(ValueError, match="Invalid regex"):
        fp.replace_in_files([str(f)], "[invalid", "x",
                             {"case_sensitive": True, "regex": True, "dry_run": False})


# ---------------------------------------------------------------------------
# rename_file
# ---------------------------------------------------------------------------

def test_rename_success(tmp_path):
    f = tmp_path / "old.txt"
    f.write_text("hello")
    result = fp.rename_file(str(f), "new.txt")
    assert result["success"] is True
    assert (tmp_path / "new.txt").exists()
    assert not f.exists()


def test_rename_no_path_separator(tmp_path):
    f = tmp_path / "file.txt"
    f.write_text("x")
    with pytest.raises(ValueError, match="Invalid file name"):
        fp.rename_file(str(f), "sub/file.txt")


def test_rename_target_exists(tmp_path):
    f1 = tmp_path / "a.txt"
    f2 = tmp_path / "b.txt"
    f1.write_text("a")
    f2.write_text("b")
    with pytest.raises(ValueError, match="already exists"):
        fp.rename_file(str(f1), "b.txt")


def test_rename_nonexistent(tmp_path):
    with pytest.raises(ValueError, match="File not found"):
        fp.rename_file(str(tmp_path / "ghost.txt"), "new.txt")


# ---------------------------------------------------------------------------
# delete_file
# ---------------------------------------------------------------------------

def test_delete_success(tmp_path):
    f = tmp_path / "todelete.txt"
    f.write_text("bye")
    result = fp.delete_file(str(f))
    assert result["success"] is True
    assert not f.exists()


def test_delete_nonexistent(tmp_path):
    with pytest.raises(ValueError, match="File not found"):
        fp.delete_file(str(tmp_path / "ghost.txt"))


# ---------------------------------------------------------------------------
# download_single_file
# ---------------------------------------------------------------------------

def test_download_single_returns_bytes(tmp_path):
    f = tmp_path / "data.txt"
    f.write_text("content here")
    data, mime, filename = fp.download_single_file(str(f))
    assert isinstance(data, bytes)
    assert filename == "data.txt"
    assert mime  # some MIME type


def test_download_zip_multiple_files(tmp_path):
    f1 = tmp_path / "a.txt"
    f2 = tmp_path / "b.txt"
    f1.write_text("alpha")
    f2.write_text("beta")
    zip_data, zip_name = fp.download_files_as_zip([str(f1), str(f2)])
    assert isinstance(zip_data, bytes)
    assert zip_name.startswith("downloaded_files_")
    assert zip_name.endswith(".zip")
    # Validate it's a real ZIP
    import io, zipfile
    with zipfile.ZipFile(io.BytesIO(zip_data)) as zf:
        names = zf.namelist()
    assert "a.txt" in names or any("a.txt" in n for n in names)
    assert "b.txt" in names or any("b.txt" in n for n in names)


# ---------------------------------------------------------------------------
# get_file_contents with block filtering
# ---------------------------------------------------------------------------

def test_get_file_contents_no_blocks(tmp_path):
    f = tmp_path / "test.js"
    f.write_text("function foo() { return 1; }\nfunction bar() { return 2; }")
    result = fp.get_file_contents([str(f)], {})
    assert len(result) == 1
    assert "foo" in result[0]["content"]
    assert "bar" in result[0]["content"]


def test_get_file_contents_empty_blocks_returns_full(tmp_path):
    f = tmp_path / "test.js"
    f.write_text("function foo() { return 1; }")
    result = fp.get_file_contents([str(f)], {str(f): []})
    assert "foo" in result[0]["content"]


def test_get_file_contents_outline(tmp_path):
    f = tmp_path / "test.js"
    f.write_text("function greet(name) { return 'hello ' + name; }")
    result = fp.get_file_contents_outline([str(f)])
    assert len(result) == 1
    assert "greet" in result[0]["content"]


# ---------------------------------------------------------------------------
# list_content_blocks
# ---------------------------------------------------------------------------

def test_list_content_blocks_js(tmp_path):
    f = tmp_path / "test.js"
    f.write_text("function foo() { return 1; }\nfunction bar() { return 2; }")
    blocks = fp.list_content_blocks(str(f))
    assert len(blocks) >= 2
    sigs = [b["signature"] for b in blocks]
    assert any("foo" in s for s in sigs)
    assert any("bar" in s for s in sigs)


def test_list_content_blocks_php():
    src_path = str(FIXTURES / "sample.php")
    blocks = fp.list_content_blocks(src_path)
    sigs = [b["signature"] for b in blocks]
    assert any("getUser" in s for s in sigs)
    assert any("createUser" in s for s in sigs)


def test_list_content_blocks_md():
    src_path = str(FIXTURES / "sample.md")
    blocks = fp.list_content_blocks(src_path)
    sigs = [b["signature"] for b in blocks]
    assert any("Section One" in s for s in sigs)
    assert any("Section Two" in s for s in sigs)


def test_list_content_blocks_unreadable_returns_empty(tmp_path):
    result = fp.list_content_blocks(str(tmp_path / "nonexistent.js"))
    assert result == []
