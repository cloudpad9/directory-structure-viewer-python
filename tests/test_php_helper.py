"""Tests for php_helper module."""
from pathlib import Path

import pytest

from dsviewer import php_helper
from dsviewer.utils import offset_to_line_number

FIXTURES = Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------------------
# get_block_signatures
# ---------------------------------------------------------------------------

def test_detects_public_function():
    src = "class Foo {\n    public function bar() { return 1; }\n}"
    sigs = php_helper.get_block_signatures(src)
    names = [s[0] for s in sigs]
    assert any("bar" in n for n in names)


def test_detects_private_static():
    src = "class Foo {\n    private static function baz($x) { return $x; }\n}"
    sigs = php_helper.get_block_signatures(src)
    assert any("baz" in s[0] for s in sigs)


def test_detects_all_visibility_modifiers():
    src = (
        "public function a() {}\n"
        "protected function b() {}\n"
        "private function c() {}\n"
        "function d() {}\n"
    )
    sigs = php_helper.get_block_signatures(src)
    names_str = " ".join(s[0] for s in sigs)
    for fn in ("a", "b", "c", "d"):
        assert fn in names_str


def test_line_numbers_correct():
    src = "function foo() {}\nfunction bar() {}"
    sigs = php_helper.get_block_signatures(src)
    assert sigs[0][2] == 1
    assert sigs[1][2] == 2


def test_fixture_php():
    src = (FIXTURES / "sample.php").read_text()
    sigs = php_helper.get_block_signatures(src)
    sig_names = " ".join(s[0] for s in sigs)
    assert "__construct" in sig_names
    assert "getUser" in sig_names
    assert "validateEmail" in sig_names
    assert "hashPassword" in sig_names
    assert "createUser" in sig_names


# ---------------------------------------------------------------------------
# cleanup_content
# ---------------------------------------------------------------------------

def test_removes_empty_class():
    src = "class Empty {\n\n}\nfunction foo() { return 1; }"
    cleaned = php_helper.cleanup_content(src)
    assert "class Empty" not in cleaned
    assert "foo" in cleaned


def test_removes_use_statements():
    src = "use Foo\\Bar;\nuse Baz;\nfunction hello() { return 1; }"
    cleaned = php_helper.cleanup_content(src)
    assert "use Foo" not in cleaned
    assert "use Baz" not in cleaned
    assert "hello" in cleaned


def test_removes_multiline_comment():
    src = "/* this is a comment */\nfunction foo() { return 1; }"
    cleaned = php_helper.cleanup_content(src)
    assert "this is a comment" not in cleaned
    assert "foo" in cleaned


def test_removes_single_line_comment():
    src = "// a comment\nfunction foo() { return 1; }"
    cleaned = php_helper.cleanup_content(src)
    assert "a comment" not in cleaned


def test_collapses_blank_lines():
    src = "function foo() { return 1; }\n\n\n\nfunction bar() {}"
    cleaned = php_helper.cleanup_content(src)
    # Should not have 3+ consecutive blank lines
    assert "\n\n\n" not in cleaned
