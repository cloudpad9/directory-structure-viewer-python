"""
markdown_helper.py — Port of PHP MarkdownHelper + MarkdownBlockHelper classes.
"""
from __future__ import annotations

import re

from dsviewer.utils import offset_to_line_number, remove_redundant_blank_lines

_MD_HEADING_RE = re.compile(r"^(#{2,3}\s.+)$", re.MULTILINE)


def get_block_signatures(content: str) -> list:
    """Return [[heading_text, offset, line_number], ...] for h2/h3 headings."""
    results = []
    for m in _MD_HEADING_RE.finditer(content):
        results.append([m.group(0).strip(), m.start(), offset_to_line_number(content, m.start())])
    return results


def get_block_contents(content: str) -> dict[int, str]:
    sigs = get_block_signatures(content)
    return _get_block_contents_from_signatures(content, sigs)


def cleanup_content(content: str) -> str:
    return remove_redundant_blank_lines(content)


# ---------------------------------------------------------------------------
# Markdown-specific block content extraction (heading-extent model)
# ---------------------------------------------------------------------------

_ANY_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)


def _get_block_content_from_signature(content: str, signature: str, start_pos: int) -> str:
    """
    Block spans from `start_pos` to the next heading of same or higher level
    (fewer #), or end of content if none.
    """
    sig_level = signature.count("#")

    end_pos = len(content)
    search_from = start_pos + len(signature)

    for m in _ANY_HEADING_RE.finditer(content, search_from):
        current_level = len(m.group(1))
        if current_level <= sig_level:
            end_pos = m.start()
            break

    return content[start_pos:end_pos]


def _get_block_contents_from_signatures(content: str, signatures: list) -> dict[int, str]:
    blocks: dict[int, str] = {}
    for sig_info in signatures:
        offset = sig_info[1]
        blocks[offset] = _get_block_content_from_signature(content, sig_info[0], offset)
    return blocks
