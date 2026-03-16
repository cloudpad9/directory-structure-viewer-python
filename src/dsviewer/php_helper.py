"""
php_helper.py — Port of PHP PhpHelper class.
"""
from __future__ import annotations

import re

from dsviewer.block_helpers import get_block_contents_from_signatures
from dsviewer.utils import offset_to_line_number, remove_redundant_blank_lines, remove_comments

_PHP_FUNC_RE = re.compile(
    r"\b(?:(?:public|protected|private|static|final|abstract)\s+)*"
    r"function\s+([a-zA-Z_]\w*)\s*\(",
    re.IGNORECASE,
)


def get_block_signatures(content: str) -> list:
    """Return [[match_text, offset, line_number], ...] for all PHP function declarations."""
    results = []
    for m in _PHP_FUNC_RE.finditer(content):
        results.append([m.group(0), m.start(), offset_to_line_number(content, m.start())])
    return results


def get_block_contents(content: str) -> dict[int, str]:
    sigs = get_block_signatures(content)
    return get_block_contents_from_signatures(content, sigs)


def cleanup_content(content: str) -> str:
    content = _remove_empty_blocks(content)
    content = _remove_use_statements(content)
    content = remove_comments(content)
    content = remove_redundant_blank_lines(content)
    return content


def _remove_empty_blocks(content: str) -> str:
    return re.sub(r"class\s+(\w+)\s*\{[\s\n]*\}", "", content)


def _remove_use_statements(content: str) -> str:
    lines = content.split("\n")
    cleaned = [ln for ln in lines if not re.match(r"^\s*use\s+", ln.strip())]
    return "\n".join(cleaned)
