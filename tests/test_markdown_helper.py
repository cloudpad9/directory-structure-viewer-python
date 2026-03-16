"""Tests for markdown_helper module."""
from pathlib import Path

import pytest

from dsviewer import markdown_helper

FIXTURES = Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------------------
# get_block_signatures
# ---------------------------------------------------------------------------

def test_detects_h2():
    src = "# Title\n\n## Section One\n\nContent here.\n"
    sigs = markdown_helper.get_block_signatures(src)
    assert any("Section One" in s[0] for s in sigs)


def test_detects_h3():
    src = "## Parent\n\n### Child\n\nContent.\n"
    sigs = markdown_helper.get_block_signatures(src)
    texts = [s[0] for s in sigs]
    assert any("Parent" in t for t in texts)
    assert any("Child" in t for t in texts)


def test_ignores_h1():
    src = "# Top Level\n\n## Section\n"
    sigs = markdown_helper.get_block_signatures(src)
    texts = [s[0] for s in sigs]
    assert not any("Top Level" in t for t in texts)
    assert any("Section" in t for t in texts)


def test_ignores_h4_and_deeper():
    src = "## H2\n\n#### H4 skipped\n"
    sigs = markdown_helper.get_block_signatures(src)
    texts = [s[0] for s in sigs]
    assert not any("H4" in t for t in texts)
    assert any("H2" in t for t in texts)


def test_line_numbers():
    src = "## First\n\nContent.\n\n## Second\n"
    sigs = markdown_helper.get_block_signatures(src)
    assert sigs[0][2] == 1
    assert sigs[1][2] == 5


def test_fixture_md():
    src = (FIXTURES / "sample.md").read_text()
    sigs = markdown_helper.get_block_signatures(src)
    texts = " ".join(s[0] for s in sigs)
    assert "Section One" in texts
    assert "Section Two" in texts
    assert "Subsection 1.1" in texts
    assert "Subsection 2.1" in texts


# ---------------------------------------------------------------------------
# Block content extraction (heading-extent model)
# ---------------------------------------------------------------------------

def test_block_ends_at_next_same_level():
    src = "## Alpha\n\nAlpha content.\n\n## Beta\n\nBeta content.\n"
    contents = markdown_helper.get_block_contents(src)
    # Alpha block should not contain Beta
    alpha_content = next(v for v in contents.values() if "Alpha" in v)
    assert "Beta content" not in alpha_content


def test_h3_block_ends_at_h2():
    src = "## Parent\n\n### Child\n\nChild content.\n\n## Sibling\n\nSibling content.\n"
    sigs = markdown_helper.get_block_signatures(src)
    contents = markdown_helper.get_block_contents(src)
    # Child block should end before Sibling
    child_sig = next(s for s in sigs if "Child" in s[0])
    child_content = contents[child_sig[1]]
    assert "Sibling content" not in child_content


def test_last_block_extends_to_eof():
    src = "## Only Section\n\nAll the content.\nMore content.\n"
    contents = markdown_helper.get_block_contents(src)
    assert len(contents) == 1
    only = next(iter(contents.values()))
    assert "All the content" in only
    assert "More content" in only


# ---------------------------------------------------------------------------
# cleanup_content
# ---------------------------------------------------------------------------

def test_cleanup_collapses_blank_lines():
    src = "## Section\n\n\n\nContent here.\n"
    cleaned = markdown_helper.cleanup_content(src)
    assert "\n\n\n" not in cleaned
