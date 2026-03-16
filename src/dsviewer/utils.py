"""
utils.py — Shared utility functions (port of PHP Util class).
"""
from __future__ import annotations

import re


def offset_to_line_number(content: str, offset: int) -> int:
    """
    Port of PHP: substr_count(substr(trim($content), 0, $offset), "\\n") + 1
    Trim the entire content first, then take the prefix up to $offset, then count newlines.
    NOTE: The spec code example has this backwards — trim must apply to the full content
    before slicing, which matches the PHP substr(trim(...), 0, $offset) behaviour.
    """
    return content.strip()[:offset].count("\n") + 1


def remove_redundant_blank_lines(content: str) -> str:
    """Collapse consecutive blank lines into single blank lines."""
    lines = content.split("\n")
    cleaned: list[str] = []
    previous_blank = False

    for line in lines:
        is_blank = line.strip() == ""
        if not (is_blank and previous_blank):
            cleaned.append(line)
        previous_blank = is_blank

    return "\n".join(cleaned)


def remove_comments(content: str) -> str:
    """Remove multi-line /* */, single-line //, and shell-style # comments."""
    # Multi-line /* ... */
    content = re.sub(r"/\*[\s\S]*?\*/", "", content)
    # Single-line //
    content = re.sub(r"//.*$", "", content, flags=re.MULTILINE)
    # Shell-style # (only at start of line, allowing leading whitespace)
    content = re.sub(r"^\s*#.*$", "", content, flags=re.MULTILINE)
    return content
