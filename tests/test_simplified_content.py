"""Tests for simplified_content module."""
import pytest

from dsviewer.simplified_content import (
    get_simplified_content,
    js_mask,
    normalize_assigned_signature,
    js_is_control_flow_before,
    find_matching_brace_js,
    looks_like_regex_start,
)


# ---------------------------------------------------------------------------
# js_mask
# ---------------------------------------------------------------------------

def test_mask_replaces_string_contents():
    src = 'const x = "hello world";'
    masked = js_mask(src)
    # String content should be spaces, but outer structure preserved
    assert "hello" not in masked
    assert "const" in masked


def test_mask_preserves_newlines():
    src = 'const a = "line1";\nconst b = "line2";'
    masked = js_mask(src)
    assert masked.count("\n") == src.count("\n")


def test_mask_replaces_single_quote_string():
    src = "const y = 'secret';"
    masked = js_mask(src)
    assert "secret" not in masked


def test_mask_replaces_template_literal():
    src = "const z = `template ${expr} end`;"
    masked = js_mask(src)
    assert "template" not in masked


def test_mask_replaces_line_comment():
    src = "const x = 1; // this is a comment\nconst y = 2;"
    masked = js_mask(src)
    assert "this is a comment" not in masked
    assert "const y" in masked


def test_mask_replaces_block_comment():
    src = "/* block comment */\nconst x = 1;"
    masked = js_mask(src)
    assert "block comment" not in masked
    assert "const x" in masked


def test_mask_preserves_braces():
    src = "function foo() { return 1; }"
    masked = js_mask(src)
    assert "{" in masked
    assert "}" in masked


# ---------------------------------------------------------------------------
# find_matching_brace_js
# ---------------------------------------------------------------------------

def test_finds_simple_matching_brace():
    src = "{ return 1; }"
    assert find_matching_brace_js(src, 0) == len(src) - 1


def test_finds_nested_brace():
    src = "{ if (x) { return 1; } return 2; }"
    result = find_matching_brace_js(src, 0)
    assert result == len(src) - 1


def test_ignores_brace_in_string():
    src = '{ let s = "{not a brace}"; return s; }'
    result = find_matching_brace_js(src, 0)
    assert result == len(src) - 1


def test_returns_minus_one_for_unmatched():
    src = "{ no closing brace"
    assert find_matching_brace_js(src, 0) == -1


# ---------------------------------------------------------------------------
# normalize_assigned_signature
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("input_sig, expected", [
    ("const foo = function(a, b)", "function foo(a, b)"),
    ("const foo = (a, b) =>", "function foo(a, b)"),
    ("const foo = a =>", "function foo(a)"),
    ("export const foo = (a) =>", "function foo(a)"),
    ("let bar = (x, y) =>", "function bar(x, y)"),
    ("var baz = function(z)", "function baz(z)"),
    ("myProp: function(a, b)", "function myProp(a, b)"),
    ("myProp: (a) =>", "function myProp(a)"),
])
def test_normalize_variants(input_sig, expected):
    assert normalize_assigned_signature(input_sig) == expected


def test_normalize_class_field_arrow():
    sig = "handleClick = (e) =>"
    result = normalize_assigned_signature(sig)
    assert result == "function handleClick(e)"


def test_normalize_private_field():
    sig = "#privateFn = (a) =>"
    result = normalize_assigned_signature(sig)
    assert "privateFn" in result


def test_normalize_passthrough_for_unknown():
    sig = "something weird"
    assert normalize_assigned_signature(sig) == "something weird"


# ---------------------------------------------------------------------------
# js_is_control_flow_before
# ---------------------------------------------------------------------------

def test_detects_if_before_brace():
    mask = "if (condition) "
    assert js_is_control_flow_before(mask, len(mask))


def test_detects_for_before_brace():
    mask = "for (let i = 0; i < n; i++) "
    assert js_is_control_flow_before(mask, len(mask))


def test_does_not_flag_function():
    mask = "function foo() "
    assert not js_is_control_flow_before(mask, len(mask))


def test_does_not_flag_class():
    mask = "class Foo "
    assert not js_is_control_flow_before(mask, len(mask))


# ---------------------------------------------------------------------------
# get_simplified_content — integration
# ---------------------------------------------------------------------------

def test_empty_content():
    result = get_simplified_content("")
    assert "(empty)" in result


def test_simple_function_outline():
    src = "function greet(name) { return 'hello ' + name; }"
    result = get_simplified_content(src)
    assert "greet" in result
    assert ";" in result  # leaf function rendered as signature;


def test_class_outline():
    src = """
class Animal {
    constructor(name) {
        this.name = name;
    }
    speak() {
        return this.name + ' makes a noise.';
    }
}
"""
    result = get_simplified_content(src)
    assert "class Animal" in result
    assert "constructor" in result
    assert "speak" in result
    # Class body methods should end with ;
    assert ";" in result


def test_nested_function_with_children():
    src = """
function outer() {
    function inner() {
        return 1;
    }
    return inner();
}
"""
    result = get_simplified_content(src)
    assert "outer" in result
    assert "inner" in result
    # outer has children so renders with braces
    assert "{" in result


def test_no_declarations():
    src = "const x = 1;\nconst y = 2;\n"
    result = get_simplified_content(src)
    # No block-bodied declarations → fallback message
    assert "no declarations found" in result or result.strip() == ""


def test_export_default_container():
    src = """
export default {
    data() { return {}; },
    methods: {
        fetchData() { return null; }
    }
}
"""
    result = get_simplified_content(src)
    assert "export default" in result
    assert "data" in result


def test_async_function():
    src = "async function loadUser(id) { const u = await db.find(id); return u; }"
    result = get_simplified_content(src)
    assert "loadUser" in result


def test_arrow_function_assigned():
    src = "const process = (item) => { return item.id; }"
    result = get_simplified_content(src)
    assert "process" in result
