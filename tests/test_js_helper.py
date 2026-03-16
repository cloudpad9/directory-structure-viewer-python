"""Tests for js_helper module."""
from pathlib import Path

import pytest

from dsviewer import js_helper

FIXTURES = Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------------------
# get_block_signatures
# ---------------------------------------------------------------------------

def test_detects_named_function():
    src = "function greet(name) { return name; }"
    sigs = js_helper.get_block_signatures(src)
    assert any("greet" in s[0] for s in sigs)


def test_detects_const_arrow():
    src = "const add = (a, b) => { return a + b; }"
    sigs = js_helper.get_block_signatures(src)
    assert any("add" in s[0] for s in sigs)


def test_detects_const_function():
    src = "const multiply = function(x, y) { return x * y; }"
    sigs = js_helper.get_block_signatures(src)
    assert any("multiply" in s[0] for s in sigs)


def test_detects_style_block():
    src = "<style>\n.foo { color: red; }\n</style>"
    sigs = js_helper.get_block_signatures(src)
    types = [s[3] for s in sigs]
    assert "STYLE" in types


def test_detects_const_object():
    src = "const config = { key: 'value', other: 42 }"
    sigs = js_helper.get_block_signatures(src)
    assert any("config" in s[0] for s in sigs)


def test_deduplication_same_line():
    # Two patterns might match the same line; only smallest offset should survive
    src = "const foo = (x) => { return x; }"
    sigs = js_helper.get_block_signatures(src)
    line_numbers = [s[2] for s in sigs]
    # No duplicate line numbers
    assert len(line_numbers) == len(set(line_numbers))


def test_line_numbers():
    src = "function a() { }\nfunction b() { }\nfunction c() { }"
    sigs = js_helper.get_block_signatures(src)
    lns = sorted(s[2] for s in sigs)
    assert lns == [1, 2, 3]


def test_fixture_js():
    src = (FIXTURES / "sample.js").read_text()
    sigs = js_helper.get_block_signatures(src)
    sig_text = " ".join(s[0] for s in sigs)
    assert "greet" in sig_text
    assert "add" in sig_text
    assert "fetchData" in sig_text
    # Note: `const multiply = function(x,y)` and `class Calculator` have no matching
    # pattern in JavascriptHelper (faithful port of PHP) — simplified_content handles classes.


def test_fixture_vue():
    src = (FIXTURES / "sample.vue").read_text()
    sigs = js_helper.get_block_signatures(src)
    types = [s[3] for s in sigs]
    assert "STYLE" in types
    assert "APP_DIV" in types


# ---------------------------------------------------------------------------
# cleanup_content
# ---------------------------------------------------------------------------

def test_removes_svgs():
    src = "const x = 1;\n<svg xmlns='...'><path/></svg>\nconst y = 2;"
    cleaned = js_helper.cleanup_content(src)
    assert "<svg" not in cleaned
    assert "const x" in cleaned
    assert "const y" in cleaned


def test_removes_blank_code_lines():
    src = "const x = 1;\n;\nconst y = 2;"
    cleaned = js_helper.cleanup_content(src)
    lines = [ln for ln in cleaned.split("\n") if ln.strip() == ";"]
    assert len(lines) == 0


def test_removes_empty_class():
    src = "class Empty {\n}\nfunction foo() {}"
    cleaned = js_helper.cleanup_content(src)
    assert "class Empty" not in cleaned
    assert "foo" in cleaned


def test_collapses_blank_lines():
    src = "const a = 1;\n\n\n\nconst b = 2;"
    cleaned = js_helper.cleanup_content(src)
    assert "\n\n\n" not in cleaned
