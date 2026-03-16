"""Tests for block_helpers module."""
import pytest

from dsviewer.block_helpers import (
    get_block_content_function,
    get_block_content,
    get_block_infos_from_signatures,
    get_block_contents_from_signatures,
)


# ---------------------------------------------------------------------------
# get_block_content_function
# ---------------------------------------------------------------------------

def test_simple_function_block():
    src = "function foo() { return 1; }"
    result = get_block_content_function(src, "function foo()", 13)
    assert result == "{ return 1; }"


def test_nested_braces():
    src = "function foo() { if (x) { return 1; } return 2; }"
    result = get_block_content_function(src, "function foo()", 15)
    assert result == "{ if (x) { return 1; } return 2; }"


def test_string_with_brace_inside():
    src = 'function foo() { let s = "a{b}c"; return s; }'
    result = get_block_content_function(src, "function foo()", 15)
    assert result == '{ let s = "a{b}c"; return s; }'


def test_single_quote_string_with_brace():
    src = "function foo() { let s = 'a{b}c'; return s; }"
    result = get_block_content_function(src, "function foo()", 15)
    assert result == "{ let s = 'a{b}c'; return s; }"


def test_quote_reset_on_newline():
    # Unclosed quote on one line should not bleed into the next
    src = "function foo() {\n  let x = 1;\n  return x;\n}"
    result = get_block_content_function(src, "function foo()", 15)
    assert result.startswith("{")
    assert result.endswith("}")


def test_unmatched_brace_raises():
    src = "function foo() { no closing brace"
    with pytest.raises(RuntimeError, match="Unmatched braces"):
        get_block_content_function(src, "function foo()", 15)


# ---------------------------------------------------------------------------
# get_block_content dispatch
# ---------------------------------------------------------------------------

def test_style_block():
    src = "<style>.foo { color: red; }</style>"
    result = get_block_content(src, "<style>", 0, "STYLE")
    assert result == "<style>.foo { color: red; }</style>"


def test_style_block_missing_close_raises():
    src = "<style>.foo { color: red; }"
    with pytest.raises(RuntimeError, match="Closing style tag not found"):
        get_block_content(src, "<style>", 0, "STYLE")


def test_app_div_block():
    src = '<div id="app"><div class="inner">hi</div></div>'
    result = get_block_content(src, '<div id="app"', 0, "APP_DIV")
    assert result == src


def test_app_div_nested():
    src = '<div id="app"><div><div>deep</div></div></div> extra'
    result = get_block_content(src, '<div id="app"', 0, "APP_DIV")
    assert result == '<div id="app"><div><div>deep</div></div></div>'


def test_default_dispatches_to_function():
    src = "myMethod() { return 42; }"
    result = get_block_content(src, "myMethod()", 10, "")
    assert result == "{ return 42; }"


# ---------------------------------------------------------------------------
# get_block_infos_from_signatures
# ---------------------------------------------------------------------------

def test_block_infos_basic():
    src = "function foo() { return 1; } function bar() { return 2; }"
    sigs = [
        ["function foo()", 0, 1],
        ["function bar()", 29, 1],
    ]
    infos = get_block_infos_from_signatures(src, sigs)
    assert len(infos) == 2
    assert infos[0]["signature"] == "function foo()"
    assert infos[0]["offset"] == 0
    assert infos[0]["parentOffsets"] == []
    assert infos[1]["parentOffsets"] == []


def test_block_infos_parent_detection():
    src = "class Foo { method() { return 1; } }"
    # Simulate: class Foo at 0, method at 12
    sigs = [
        ["class Foo", 0, 1],
        ["method()", 12, 2],
    ]
    infos = get_block_infos_from_signatures(src, sigs)
    assert infos[1]["offset"] == 12
    assert 0 in infos[1]["parentOffsets"]


def test_block_infos_sorted_by_offset():
    src = "function b() { } function a() { }"
    sigs = [
        ["function b()", 0, 1],
        ["function a()", 17, 1],
    ]
    infos = get_block_infos_from_signatures(src, sigs)
    assert infos[0]["offset"] < infos[1]["offset"]


# ---------------------------------------------------------------------------
# get_block_contents_from_signatures
# ---------------------------------------------------------------------------

def test_get_block_contents():
    src = "function foo() { return 1; }"
    sigs = [["function foo()", 15, 1]]
    contents = get_block_contents_from_signatures(src, sigs)
    assert 15 in contents
    assert contents[15] == "{ return 1; }"
