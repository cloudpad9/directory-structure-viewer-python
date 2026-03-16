"""
js_helper.py — Port of PHP JavascriptHelper class.
"""
from __future__ import annotations

import re

from dsviewer.block_helpers import get_block_contents_from_signatures
from dsviewer.utils import offset_to_line_number, remove_redundant_blank_lines

# ---------------------------------------------------------------------------
# Patterns (match PHP exactly)
# ---------------------------------------------------------------------------

PATTERNS: dict[str, re.Pattern] = {
    "CONST_ARROW": re.compile(
        r"\b(?:(const|let|var)\s+)([a-zA-Z_$][0-9a-zA-Z_$]*)\s*=\s*(?:async\s+)?"
        r"(?:\(\s*.*?\s*\)\s*=>|([a-zA-Z_$][0-9a-zA-Z_$]*\s*=>))"
    ),
    "FUNCTION": re.compile(
        r"\b(?:async\s+)?function\s+([a-zA-Z_$][0-9a-zA-Z_$]*)\s*\("
    ),
    "METHOD": re.compile(
        r"\b(?:async\s+)?([a-zA-Z_$][0-9a-zA-Z_$]*)\s*\(\s*\)\s*\{"
    ),
    "STYLE": re.compile(r"<style[^>]*>"),
    "CONST_OBJECT": re.compile(
        r"\b(?:(const|let|var)\s+)([a-zA-Z_$][0-9a-zA-Z_$]*)\s*=\s*\{"
    ),
    "APP_DIV": re.compile(r'<div\s+id="app"'),
}


def get_block_signatures(content: str) -> list:
    """
    Apply each pattern, collect matches with type, sort by line number,
    then deduplicate (same line → keep smallest offset).
    """
    blocks: list = []

    for type_name, pattern in PATTERNS.items():
        for m in pattern.finditer(content):
            ln = offset_to_line_number(content, m.start())
            blocks.append([m.group(0), m.start(), ln, type_name])

    # Sort by line number ascending
    blocks.sort(key=lambda b: b[2])

    return _remove_duplicates(blocks)


def _remove_duplicates(blocks: list) -> list:
    """Keep only the match with the smallest offset per line number."""
    unique: list = []
    last_line = -1
    last_offset = float("inf")

    for block in blocks:
        if block[2] != last_line:
            unique.append(block)
            last_line = block[2]
            last_offset = block[1]
        elif block[1] < last_offset:
            unique[-1] = block
            last_offset = block[1]

    return unique


def get_block_contents(content: str) -> dict[int, str]:
    sigs = get_block_signatures(content)
    return get_block_contents_from_signatures(content, sigs)


def cleanup_content(content: str) -> str:
    content = _remove_empty_blocks(content)
    content = _remove_svgs(content)
    content = _remove_blank_code_lines(content)
    content = remove_redundant_blank_lines(content)
    return content


def _remove_empty_blocks(content: str) -> str:
    return re.sub(r"class\s+(\w+)\s*\{[\s\n]*\}", "", content)


def _remove_svgs(content: str) -> str:
    return re.sub(r"<svg\b[^>]*>.*?</svg>", "", content, flags=re.IGNORECASE | re.DOTALL)


def _remove_blank_code_lines(content: str) -> str:
    lines = content.split("\n")
    cleaned = [ln for ln in lines if ln.strip() != ";"]
    return "\n".join(cleaned)
