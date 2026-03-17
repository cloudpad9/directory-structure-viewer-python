"""
block_helpers.py — Port of PHP BlockHelper class.

Provides brace-matched block extraction and block-info computation.
"""
from __future__ import annotations


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_block_infos_from_signatures(content: str, signatures: list) -> list[dict]:
    """
    Input:  signatures = list of [signature_text, offset, line_number, type?]
    Output: list of {signature, offset, endPos, lineNumber, parentOffsets}
    """
    signatures = sorted(signatures, key=lambda s: s[1])

    block_infos: list[dict] = []
    offsets = [s[1] for s in signatures]

    for i, sig_info in enumerate(signatures):
        signature = sig_info[0]
        offset = sig_info[1]
        line_number = sig_info[2]
        block_type = sig_info[3] if len(sig_info) > 3 else ""

        block_content = get_block_content(content, signature, offset, block_type)
        # block_content bắt đầu từ { (không phải từ offset của match),
        # nên tìm vị trí thực của block_content trong content để tính end_pos chính xác
        actual_start = content.find(block_content, offset)
        if actual_start == -1:
            actual_start = offset
        end_pos = actual_start + len(block_content)

        parent_offsets: list[int] = []
        for j in range(i):
            existing_offset = offsets[j]
            if existing_offset < offset and block_infos[j]["endPos"] > end_pos:
                parent_offsets.append(existing_offset)
                # Merge parent's parents (deep ancestry)
                parent_offsets.extend(block_infos[j]["parentOffsets"])

        block_infos.append({
            "signature": signature,
            "offset": offset,
            "endPos": end_pos,
            "lineNumber": line_number,
            "parentOffsets": list(dict.fromkeys(parent_offsets)),  # unique, preserve order
        })

    return block_infos


def get_block_contents_from_signatures(content: str, signatures: list) -> dict[int, str]:
    """Return {offset: block_content_string} for each signature."""
    blocks: dict[int, str] = {}
    for sig_info in signatures:
        offset = sig_info[1]
        block_type = sig_info[3] if len(sig_info) > 3 else ""
        blocks[offset] = get_block_content(content, sig_info[0], offset, block_type)
    return blocks


def get_block_content(content: str, signature: str, offset: int, block_type: str) -> str:
    if block_type == "STYLE":
        return _get_block_content_style(content, signature, offset)
    if block_type == "APP_DIV":
        return _get_block_content_app_div(content, signature, offset)
    return get_block_content_function(content, signature, offset)


# ---------------------------------------------------------------------------
# Block extraction implementations
# ---------------------------------------------------------------------------

def _get_block_content_style(content: str, signature: str, start_pos: int) -> str:
    end_tag = "</style>"
    end_pos = content.find(end_tag, start_pos)
    if end_pos == -1:
        raise RuntimeError("Closing style tag not found")
    return content[start_pos: end_pos + len(end_tag)]


def get_block_content_function(content: str, signature: str, start_pos: int) -> str:
    """
    Brace-count walk — port of PHP getBlockContent_Function().
    Scan forward từ start_pos đến { đầu tiên, sau đó track brace depth.
    Tracks single/double quote state; resets on newline (same as PHP).
    """
    single_quote_count = 0
    double_quote_count = 0
    brace_count = 0
    brace_start = -1
    n = len(content)

    for i in range(start_pos, n):
        c = content[i]

        if c == "{":
            if not single_quote_count and not double_quote_count:
                brace_count += 1
                # Ghi nhận vị trí { đầu tiên để làm điểm bắt đầu kết quả
                if brace_start == -1:
                    brace_start = i
        elif c == "}":
            if not single_quote_count and not double_quote_count:
                brace_count -= 1
            if brace_count == 0 and brace_start != -1:
                return content[brace_start: i + 1]
        elif c == "'":
            single_quote_count = 0 if single_quote_count else 1
        elif c == '"':
            double_quote_count = 0 if double_quote_count else 1
        elif c in ("\r", "\n"):
            single_quote_count = 0
            double_quote_count = 0

    raise RuntimeError(f"Unmatched braces in function block, signature = {signature}")


def _get_block_content_app_div(content: str, signature: str, start_pos: int) -> str:
    tag_stack: list[str] = []
    n = len(content)

    i = start_pos
    while i < n:
        if content[i:i + 4] == "<div":
            tag_stack.append("div")
            i += 3
        elif content[i:i + 6] == "</div>":
            if not tag_stack:
                raise RuntimeError(f"Unmatched closing div tag, signature = {signature}")
            tag_stack.pop()
            if not tag_stack:
                return content[start_pos: i + 6]
            i += 5
        i += 1

    raise RuntimeError(f"Unclosed div tag, signature = {signature}")
