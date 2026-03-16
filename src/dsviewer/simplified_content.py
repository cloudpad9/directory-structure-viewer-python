"""
simplified_content.py — Port of PHP SimplifiedContentHelper.

Generates a code outline showing only function/class/method signatures.
"""
from __future__ import annotations

import re


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def get_simplified_content(content: str, file_extension: str = "") -> str:
    src = str(content)
    if not src:
        return "// (empty)\n"

    mask = js_mask(src)
    nodes = js_scan_range(src, mask, 0, len(src), "top")
    out = render_simplified_outline(nodes)
    return out if out.strip() else "// (no declarations found)\n"


# ---------------------------------------------------------------------------
# Scanner core
# ---------------------------------------------------------------------------

def js_scan_range(src: str, mask: str, start: int, end: int, ctx: str) -> list[dict]:
    """
    Scan [start, end) and return list of AST nodes with children (recursive).
    ctx: 'top' | 'class' | 'object' | 'block'
    """
    nodes: list[dict] = []
    cursor = start

    while cursor < end:
        match = js_earliest_match(mask, cursor, ctx)
        if not match:
            break

        full_start = match["fullStart"]
        open_brace = match["openBrace"]
        sig_start = match["sigStart"]
        node_type = match["type"]

        # Skip control-flow blocks (except class/container)
        if node_type not in ("class", "container"):
            if js_is_control_flow_before(mask, open_brace):
                cursor = full_start + 1
                continue

        close_brace = find_matching_brace_js(src, open_brace)
        if close_brace < 0 or close_brace > end:
            cursor = full_start + 1
            continue

        # Raw signature from src
        sig = src[sig_start:open_brace].rstrip()

        # Normalize assigned/arrow/field/property signatures
        if node_type in ("assigned", "classField", "propAssigned"):
            sig = normalize_assigned_signature(sig)

        # Determine child context
        if node_type == "class":
            child_ctx = "class"
        elif node_type == "container":
            child_ctx = "object"
        else:
            child_ctx = "block"

        children = js_scan_range(src, mask, open_brace + 1, close_brace, child_ctx)

        nodes.append({
            "kind": node_type,
            "signature": sig,
            "full": src[sig_start: close_brace + 1],
            "bodyStart": open_brace + 1,
            "bodyEnd": close_brace,
            "children": children,
        })

        cursor = close_brace + 1

    return nodes


# ---------------------------------------------------------------------------
# Pattern definitions (mirror PHP jsEarliestMatch)
# ---------------------------------------------------------------------------

_PATTERNS: dict[str, re.Pattern] = {
    "container": re.compile(
        r"((?:export\s+default)\s*)\{",
        re.MULTILINE,
    ),
    "class": re.compile(
        r"(((?:export\s+(?:default\s+)?)?\s*class)\s+[A-Za-z_\$][A-Za-z0-9_\$]*"
        r"(?:\s*<[^{}>]*>)?"
        r"(?:\s+extends\s+[^{]+)?"
        r"(?:\s+implements\s+[^{]+)?)\s*\{",
        re.MULTILINE,
    ),
    "function": re.compile(
        r"(((?:export\s+(?:default\s+)?)?(?:async\s+)?function)\s+[A-Za-z_\$][A-Za-z0-9_\$]*"
        r"(?:\s*<[^{}>]*>)?\s*\([^)]*\)\s*(?::\s*[^;{]+)?)\s*\{",
        re.MULTILINE,
    ),
    "anon": re.compile(
        r"(((?:export\s+(?:default\s+)?)?(?:async\s+)?function)\s*\([^)]*\)\s*(?::\s*[^;{]+)?)\s*\{",
        re.MULTILINE,
    ),
    "assigned": re.compile(
        r"(((?:export\s+)?(?:const|let|var)\s+[A-Za-z_\$][A-Za-z0-9_\$]*\s*=\s*(?:async\s*)?"
        r"(?:function\s*\([^)]*\)|\([^)]*\)\s*=>|[A-Za-z_\$][A-Za-z0-9_\$]*\s*=>)\s*(?::\s*[^;{]+)?))\s*\{",
        re.MULTILINE,
    ),
    "classField": re.compile(
        r"(?<!\S)"
        r"("
        r"(?:(?:public|private|protected|readonly|override|abstract|static)\s+)*"
        r"#?[A-Za-z_\$][A-Za-z0-9_\$]*"
        r"(?:\s*:\s*[^=]+)?\s*=\s*(?:async\s*)?"
        r"(?:function\s*\([^)]*\)|\([^)]*\)\s*=>|[A-Za-z_\$][A-Za-z0-9_\$]*\s*=>)"
        r"(?:\s*:\s*[^;{]+)?"
        r")\s*\{",
        re.MULTILINE,
    ),
    "propAssigned": re.compile(
        r"(?<!\S)"
        r"("
        r"(?:#?[A-Za-z_\$][A-Za-z0-9_\$]*|\[\s*[^\]]+\s*\])"
        r"\s*:\s*(?:async\s*)?(?:function\s*\([^)]*\)|\([^)]*\)\s*=>|[A-Za-z_\$][A-Za-z0-9_\$]*\s*=>)"
        r"(?:\s*:\s*[^;{]+)?"
        r")\s*\{",
        re.MULTILINE,
    ),
    "method": re.compile(
        r"(?<!\S)"
        r"("
        r"(?:(?:public|private|protected|readonly|override|abstract|static)\s+)*"
        r"(?:async\s+)?"
        r"(?:get|set)?\s*"
        r"(?:constructor|#?[A-Za-z_\$][A-Za-z0-9_\$]*|\[\s*[^\]]+\s*\])"
        r"\s*\([^)]*\)\s*(?::\s*[^;{]+)?"
        r")\s*\{",
        re.MULTILINE,
    ),
}

_CTX_PATTERNS: dict[str, list[str]] = {
    "top":    ["container", "class", "function", "assigned", "anon"],
    "class":  ["method", "classField", "propAssigned", "function", "assigned", "anon", "class"],
    "object": ["method", "classField", "propAssigned", "function", "assigned", "anon", "class"],
    "block":  ["function", "assigned", "anon", "class"],
}


def js_earliest_match(mask: str, offset: int, ctx: str) -> dict | None:
    """Find nearest declaration match for given context. Returns match dict or None."""
    use = _CTX_PATTERNS.get(ctx, _CTX_PATTERNS["block"])
    best: dict | None = None

    for type_name in use:
        pattern = _PATTERNS[type_name]
        m = pattern.search(mask, offset)
        if not m:
            continue

        full_text = m.group(0)
        full_start = m.start()
        open_brace = full_start + len(full_text) - 1  # '{' is last char

        # sig_start: group(1) is the signature part
        try:
            sig_start = m.start(1)
        except IndexError:
            sig_start = full_start

        if best is None or full_start < best["fullStart"]:
            best = {
                "type": type_name,
                "sigStart": sig_start,
                "fullStart": full_start,
                "openBrace": open_brace,
            }

    return best


# ---------------------------------------------------------------------------
# Mask & brace helpers
# ---------------------------------------------------------------------------

def js_mask(s: str) -> str:
    """
    Mask strings, comments, template literals, and regex literals.
    Preserve newlines for correct line counting.
    Port of PHP jsMask().
    """
    n = len(s)
    out = list(s)

    in_line = False
    in_block = False
    in_sq = False
    in_dq = False
    in_bt = False
    tpl_depth = 0
    in_regex = False
    in_regex_class = False

    i = 0
    while i < n:
        c = s[i]
        p = s[i - 1] if i > 0 else ""
        nxt = s[i + 1] if i + 1 < n else ""

        # --- Inside regex literal ---
        if in_regex:
            if in_regex_class:
                if p != "\\" and c == "]":
                    in_regex_class = False
                out[i] = "\n" if c == "\n" else " "
                i += 1
                continue
            if p != "\\" and c == "[":
                in_regex_class = True
                out[i] = " "
                i += 1
                continue
            if p != "\\" and c == "/":
                in_regex = False
                out[i] = " "
                # mask flags (e.g. /a/gi)
                j = i + 1
                while j < n and re.match(r"[a-z]", s[j], re.IGNORECASE):
                    out[j] = " "
                    j += 1
                i = j
                continue
            out[i] = "\n" if c == "\n" else " "
            i += 1
            continue

        # --- Inside line comment ---
        if in_line:
            out[i] = "\n" if c == "\n" else " "
            if c == "\n":
                in_line = False
            i += 1
            continue

        # --- Inside block comment ---
        if in_block:
            out[i] = "\n" if c == "\n" else " "
            if p == "*" and c == "/":
                in_block = False
            i += 1
            continue

        # --- Inside template literal ---
        if in_bt:
            out[i] = "\n" if c == "\n" else " "
            if p == "\\":
                i += 1
                continue
            if c == "`" and tpl_depth == 0:
                in_bt = False
                i += 1
                continue
            if c == "{" and i > 0 and s[i - 1] == "$":
                tpl_depth += 1
                i += 1
                continue
            if c == "}" and tpl_depth > 0:
                tpl_depth -= 1
                i += 1
                continue
            i += 1
            continue

        # --- Inside single quote string ---
        if in_sq:
            out[i] = "\n" if c == "\n" else " "
            if p != "\\" and c == "'":
                in_sq = False
            i += 1
            continue

        # --- Inside double quote string ---
        if in_dq:
            out[i] = "\n" if c == "\n" else " "
            if p != "\\" and c == '"':
                in_dq = False
            i += 1
            continue

        # --- Open block comment ---
        if c == "/" and nxt == "*":
            in_block = True
            out[i] = " "
            out[i + 1] = " "
            i += 2
            continue

        # --- Open line comment ---
        if c == "/" and nxt == "/":
            in_line = True
            out[i] = " "
            out[i + 1] = " "
            i += 2
            continue

        # --- Open strings / template ---
        if c == "'":
            in_sq = True
            out[i] = " "
            i += 1
            continue
        if c == '"':
            in_dq = True
            out[i] = " "
            i += 1
            continue
        if c == "`":
            in_bt = True
            tpl_depth = 0
            out[i] = " "
            i += 1
            continue

        # --- Possible regex literal ---
        if c == "/" and nxt != "/" and nxt != "*":
            if looks_like_regex_start(s, i):
                in_regex = True
                out[i] = " "
                i += 1
                continue

        i += 1

    return "".join(out)


def looks_like_regex_start(s: str, pos: int) -> bool:
    """Heuristic: is '/' at pos a regex literal opener?"""
    k = pos - 1
    while k >= 0 and s[k].isspace():
        k -= 1
    if k < 0:
        return True  # start of file

    if re.match(r"[=(:,\[{;!?~+\-*\/%<>&|^]", s[k]):
        return True

    tail = s[max(0, k - 10): k + 1]
    if re.search(r"\b(return|case|throw|yield)\s*$", tail):
        return True

    return False


def js_is_control_flow_before(mask: str, brace_pos: int) -> bool:
    """True if the '{' belongs to a control-flow statement."""
    look = 260
    from_pos = max(0, brace_pos - look)
    snip = mask[from_pos:brace_pos]
    return bool(re.search(
        r"\b(if|for|while|switch|catch|with|do|try|else|finally)\s*(\([^)]*\))?\s*$",
        snip,
    ))


def find_matching_brace_js(s: str, open_pos: int) -> int:
    """
    Find '}' matching '{' at open_pos, skipping strings/comments/templates/regex.
    Returns index of matching '}' or -1 if not found.
    Port of PHP findMatchingBraceJs().
    """
    n = len(s)
    depth = 0

    in_line = False
    in_block = False
    in_sq = False
    in_dq = False
    in_bt = False
    tpl_depth = 0
    in_regex = False
    in_regex_class = False

    i = open_pos
    while i < n:
        c = s[i]
        p = s[i - 1] if i > 0 else ""
        nxt = s[i + 1] if i + 1 < n else ""

        if in_regex:
            if in_regex_class:
                if p != "\\" and c == "]":
                    in_regex_class = False
                i += 1
                continue
            if p != "\\" and c == "[":
                in_regex_class = True
                i += 1
                continue
            if p != "\\" and c == "/":
                in_regex = False
                j = i + 1
                while j < n and re.match(r"[a-z]", s[j], re.IGNORECASE):
                    j += 1
                i = j
                continue
            i += 1
            continue

        if in_line:
            if c == "\n":
                in_line = False
            i += 1
            continue

        if in_block:
            if p == "*" and c == "/":
                in_block = False
            i += 1
            continue

        if in_bt:
            if p == "\\":
                i += 1
                continue
            if c == "`" and tpl_depth == 0:
                in_bt = False
                i += 1
                continue
            if c == "{" and i > 0 and s[i - 1] == "$":
                tpl_depth += 1
                i += 1
                continue
            if c == "}" and tpl_depth > 0:
                tpl_depth -= 1
                i += 1
                continue
            i += 1
            continue

        if in_sq:
            if p != "\\" and c == "'":
                in_sq = False
            i += 1
            continue

        if in_dq:
            if p != "\\" and c == '"':
                in_dq = False
            i += 1
            continue

        if c == "/" and nxt == "*":
            in_block = True
            i += 2
            continue
        if c == "/" and nxt == "/":
            in_line = True
            i += 2
            continue

        if c == "'":
            in_sq = True
            i += 1
            continue
        if c == '"':
            in_dq = True
            i += 1
            continue
        if c == "`":
            in_bt = True
            tpl_depth = 0
            i += 1
            continue

        if c == "/" and nxt != "/" and nxt != "*":
            if looks_like_regex_start(s, i):
                in_regex = True
                i += 1
                continue

        if c == "{":
            depth += 1
            i += 1
            continue
        if c == "}":
            depth -= 1
            if depth == 0:
                return i
            i += 1
            continue

        i += 1

    return -1


# ---------------------------------------------------------------------------
# Signature normalisation
# ---------------------------------------------------------------------------

def normalize_assigned_signature(sig: str) -> str:
    """
    Convert assigned/arrow/field/property signatures to 'function name(params)'.
    Port of PHP normalizeAssignedSignature().
    """
    t = sig.strip()

    # (export )?const name = async function(a, b)
    m = re.match(
        r"^(?:export\s+)?(?:const|let|var)\s+([A-Za-z_\$][A-Za-z0-9_\$]*)\s*=\s*"
        r"(?:async\s*)?function\s*\(([^)]*)\)$",
        t,
    )
    if m:
        return f"function {m.group(1)}({m.group(2)})"

    # (export )?const name = (a,b) =>
    m = re.match(
        r"^(?:export\s+)?(?:const|let|var)\s+([A-Za-z_\$][A-Za-z0-9_\$]*)\s*=\s*"
        r"\(([^)]*)\)\s*=>$",
        t,
    )
    if m:
        return f"function {m.group(1)}({m.group(2)})"

    # (export )?const name = a =>
    m = re.match(
        r"^(?:export\s+)?(?:const|let|var)\s+([A-Za-z_\$][A-Za-z0-9_\$]*)\s*=\s*"
        r"([A-Za-z_\$][A-Za-z0-9_\$]*)\s*=>$",
        t,
    )
    if m:
        return f"function {m.group(1)}({m.group(2)})"

    # class field: (modifiers )?#?name = async function(a, b)
    m = re.match(
        r"^(?:(?:public|private|protected|readonly|override|abstract|static)\s+)*"
        r"#?([A-Za-z_\$][A-Za-z0-9_\$]*)(?:\s*:\s*[^=]+)?\s*=\s*(?:async\s*)?function\s*\(([^)]*)\)$",
        t,
    )
    if m:
        return f"function {m.group(1)}({m.group(2)})"

    # class field: name = (a,b) =>
    m = re.match(
        r"^(?:(?:public|private|protected|readonly|override|abstract|static)\s+)*"
        r"#?([A-Za-z_\$][A-Za-z0-9_\$]*)(?:\s*:\s*[^=]+)?\s*=\s*\(([^)]*)\)\s*=>$",
        t,
    )
    if m:
        return f"function {m.group(1)}({m.group(2)})"

    # class field: name = x =>
    m = re.match(
        r"^(?:(?:public|private|protected|readonly|override|abstract|static)\s+)*"
        r"#?([A-Za-z_\$][A-Za-z0-9_\$]*)(?:\s*:\s*[^=]+)?\s*=\s*([A-Za-z_\$][A-Za-z0-9_\$]*)\s*=>$",
        t,
    )
    if m:
        return f"function {m.group(1)}({m.group(2)})"

    # object prop: key: function(a, b)
    m = re.match(
        r"^(#?[A-Za-z_\$][A-Za-z0-9_\$]*|\[\s*[^\]]+\s*\])\s*:\s*(?:async\s*)?function\s*\(([^)]*)\)$",
        t,
    )
    if m:
        return f"function {m.group(1)}({m.group(2)})"

    # object prop: key: (a,b) =>
    m = re.match(
        r"^(#?[A-Za-z_\$][A-Za-z0-9_\$]*|\[\s*[^\]]+\s*\])\s*:\s*\(([^)]*)\)\s*=>$",
        t,
    )
    if m:
        return f"function {m.group(1)}({m.group(2)})"

    return t


# ---------------------------------------------------------------------------
# Render
# ---------------------------------------------------------------------------

def render_simplified_outline(nodes: list[dict], depth: int = 0, parent_ctx: str = "top") -> str:
    pad = "    " * depth
    out = ""

    for node in nodes:
        sig = node["signature"].rstrip()
        kind = node["kind"]
        has_children = bool(node.get("children"))

        if kind == "class":
            out += f"{pad}{sig} {{\n"
            out += render_simplified_outline(node["children"], depth + 1, "class")
            out += f"{pad}}}\n"
        elif kind == "container":
            out += f"{pad}{sig} {{\n"
            out += render_simplified_outline(node["children"], depth + 1, "object")
            out += f"{pad}}}\n"
        else:
            in_class_or_object = parent_ctx in ("class", "object")
            if in_class_or_object:
                out += f"{pad}{sig};\n"
            else:
                if has_children:
                    out += f"{pad}{sig} {{\n"
                    out += render_simplified_outline(node["children"], depth + 1, "block")
                    out += f"{pad}}}\n"
                else:
                    out += f"{pad}{sig};\n"

    return out
