"""
file_processor.py — Port of PHP FileProcessor class.

Handles: list_files, get_file_content, save_file_content, get_file_contents,
get_file_contents_outline, download_files, list_content_blocks,
search_in_files, replace_in_files, rename_file, delete_file,
generate_public_links, get_raw_content.
"""
from __future__ import annotations

import io
import mimetypes
import os
import zipfile
from datetime import datetime
from pathlib import Path

from dsviewer import block_helpers, js_helper, markdown_helper, php_helper
from dsviewer.auth import generate_short_token, get_path_from_token
from dsviewer.simplified_content import get_simplified_content

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_EXCLUDE_DIRS = frozenset([
    ".git", ".svn", "vendor", "node_modules", ".idea", ".vscode",
    "cache", "tmp", "temp", "logs", "dist", "build", "target",
])


# ---------------------------------------------------------------------------
# list_files
# ---------------------------------------------------------------------------

def list_files(path: str) -> list[dict]:
    """
    Recursively list files and directories under path, excluding _EXCLUDE_DIRS.
    Returns entries sorted SELF_FIRST (directory before its children).
    """
    if not os.path.isdir(path):
        return []

    results: list[dict] = []

    for dirpath, dirnames, filenames in os.walk(path, topdown=True):
        # Prune excluded directories in-place (modifies traversal)
        dirnames[:] = [d for d in dirnames if d not in _EXCLUDE_DIRS]

        # Emit the directory itself (SELF_FIRST — skip root to avoid emitting path twice)
        if dirpath != path:
            results.append({"path": dirpath, "type": "directory"})

        for fname in filenames:
            results.append({"path": os.path.join(dirpath, fname), "type": "file"})

    return results


# ---------------------------------------------------------------------------
# get_file_content / save_file_content
# ---------------------------------------------------------------------------

def get_file_content(path: str) -> str:
    if not os.path.isfile(path) or not os.access(path, os.R_OK):
        return ""
    return Path(path).read_text(encoding="utf-8", errors="replace")


def save_file_content(path: str, content: str) -> None:
    Path(path).write_text(content, encoding="utf-8")


# ---------------------------------------------------------------------------
# get_file_contents (with optional block filtering)
# ---------------------------------------------------------------------------

def get_file_contents(paths: list[str], blocks: dict) -> list[dict]:
    contents = []
    for path in paths:
        if not (os.path.isfile(path) and os.access(path, os.R_OK)):
            continue

        content = Path(path).read_text(encoding="utf-8", errors="replace")
        selected_offsets = blocks.get(path, [])

        if not selected_offsets:
            contents.append({"path": path, "content": content.strip()})
            continue

        ext = _ext(path)
        block_infos = _get_block_infos(path)
        expanded_offsets = _expand_with_parent_offsets(block_infos, selected_offsets)

        if expanded_offsets:
            deleted_ranges = _get_deleted_ranges(block_infos, expanded_offsets)
            if deleted_ranges:
                content = _delete_content_ranges(content, deleted_ranges)
                content = _cleanup_content(ext, content)

        contents.append({"path": path, "content": content.strip()})

    return contents


# ---------------------------------------------------------------------------
# get_file_contents_outline
# ---------------------------------------------------------------------------

def get_file_contents_outline(paths: list[str]) -> list[dict]:
    contents = []
    for path in paths:
        if not (os.path.isfile(path) and os.access(path, os.R_OK)):
            continue
        ext = _ext(path)
        content = Path(path).read_text(encoding="utf-8", errors="replace")
        outline = get_simplified_content(content, ext)
        contents.append({"path": path, "content": outline.strip()})
    return contents


# ---------------------------------------------------------------------------
# list_content_blocks
# ---------------------------------------------------------------------------

def list_content_blocks(path: str) -> list[dict]:
    if not os.access(path, os.R_OK):
        return []
    return _get_block_infos(path)


# ---------------------------------------------------------------------------
# search_in_files
# ---------------------------------------------------------------------------

def search_in_files(paths: list[str], pattern: str, options: dict) -> dict:
    case_sensitive = options.get("case_sensitive", True)
    use_regex = options.get("regex", False)

    matched = []
    scanned = 0
    matched_files = 0
    total_matches = 0

    for file_path in paths:
        if not (os.path.isfile(file_path) and os.access(file_path, os.R_OK)):
            continue
        scanned += 1

        content = Path(file_path).read_text(encoding="utf-8", errors="replace")
        lines = content.splitlines()  # handles \r\n, \n, \r
        file_total = 0
        line_hits = []

        for i, line in enumerate(lines):
            occ, indices = _count_occurrences(line, pattern, case_sensitive, use_regex)
            if occ > 0:
                file_total += occ
                line_hits.append({
                    "line": i + 1,
                    "occurrences": occ,
                    "indices": indices,
                    "preview": _trim_preview(line),
                })

        if file_total > 0:
            matched.append({"path": file_path, "total": file_total, "lines": line_hits})
            matched_files += 1
            total_matches += file_total

    return {
        "summary": {
            "scanned": scanned,
            "matched_files": matched_files,
            "total_matches": total_matches,
        },
        "matches": matched,
    }


# ---------------------------------------------------------------------------
# replace_in_files
# ---------------------------------------------------------------------------

def replace_in_files(
    paths: list[str],
    pattern: str,
    replacement: str,
    options: dict,
) -> dict:
    case_sensitive = options.get("case_sensitive", True)
    use_regex = options.get("regex", False)
    dry_run = options.get("dry_run", False)

    changed = []
    processed = 0
    total_replaced = 0
    changed_files = 0

    for file_path in paths:
        if not (os.path.isfile(file_path)
                and os.access(file_path, os.R_OK)
                and os.access(file_path, os.W_OK)):
            continue
        processed += 1

        content = Path(file_path).read_text(encoding="utf-8", errors="replace")
        updated, replaced = _replace_all(content, pattern, replacement, case_sensitive, use_regex)

        if replaced > 0:
            if not dry_run:
                Path(file_path).write_text(updated, encoding="utf-8")
            changed.append({"path": file_path, "replaced": replaced})
            changed_files += 1
            total_replaced += replaced

    return {
        "summary": {
            "processed": processed,
            "changed_files": changed_files,
            "total_replaced": total_replaced,
            "dry_run": dry_run,
        },
        "changed": changed,
    }


# ---------------------------------------------------------------------------
# rename_file / delete_file
# ---------------------------------------------------------------------------

def rename_file(path: str, new_name: str) -> dict:
    if not path or not new_name:
        raise ValueError("Path and new name are required")
    if not os.path.exists(path):
        raise ValueError("File not found")
    if not os.access(path, os.W_OK):
        raise ValueError("File is not writable")
    if "/" in new_name or "\\" in new_name:
        raise ValueError("Invalid file name")

    dir_path = os.path.dirname(path)
    new_path = os.path.join(dir_path, new_name)

    if os.path.exists(new_path):
        raise ValueError("A file with that name already exists")

    os.rename(path, new_path)
    return {"success": True, "new_path": new_path}


def delete_file(path: str) -> dict:
    if not path or not os.path.exists(path):
        raise ValueError("File not found")
    os.unlink(path)
    return {"success": True}


# ---------------------------------------------------------------------------
# download_files — returns (bytes, mime_type, filename)
# ---------------------------------------------------------------------------

def download_single_file(path: str) -> tuple[bytes, str, str]:
    """Returns (content_bytes, mime_type, filename)."""
    mime, _ = mimetypes.guess_type(path)
    if not mime:
        mime = "application/octet-stream"
    data = Path(path).read_bytes()
    return data, mime, os.path.basename(path)


def download_files_as_zip(paths: list[str]) -> tuple[bytes, str]:
    """
    Create an in-memory ZIP of multiple files.
    Returns (zip_bytes, suggested_filename).
    """
    # Compute common base directory for relative paths
    dirs = [os.path.dirname(p) for p in paths]
    base_dir = dirs[0] if dirs else ""
    for d in dirs[1:]:
        # Trim base_dir to common prefix
        i = 0
        max_i = min(len(base_dir), len(d))
        while i < max_i and base_dir[i] == d[i]:
            i += 1
        base_dir = base_dir[:i].rstrip(os.sep)

    if not base_dir:
        base_dir = os.path.dirname(paths[0]) if paths else ""

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for file_path in paths:
            rel = file_path.replace(base_dir, "").lstrip(os.sep)
            if not rel:
                rel = os.path.basename(file_path)
            zf.write(file_path, rel)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return buf.getvalue(), f"downloaded_files_{timestamp}.zip"


# ---------------------------------------------------------------------------
# generate_public_links
# ---------------------------------------------------------------------------

def generate_public_links(paths: list[str]) -> list[dict]:
    links = []
    for path in paths:
        if not (os.path.isfile(path) and os.access(path, os.R_OK)):
            continue
        try:
            token = generate_short_token(path)
            links.append({"path": path, "token": token})
        except Exception:
            pass
    return links


# ---------------------------------------------------------------------------
# get_raw_content — returns (bytes, mime, filename)
# ---------------------------------------------------------------------------

def get_raw_content(token: str) -> tuple[bytes, str, str]:
    file_path = get_path_from_token(token)
    if not (os.path.isfile(file_path) and os.access(file_path, os.R_OK)):
        raise FileNotFoundError("File not found or not readable")
    return download_single_file(file_path)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _ext(path: str) -> str:
    return os.path.splitext(path)[1].lstrip(".").lower()


def _get_block_infos(path: str) -> list[dict]:
    ext = _ext(path)
    content = Path(path).read_text(encoding="utf-8", errors="replace")

    if ext == "php":
        sigs = php_helper.get_block_signatures(content)
    elif ext == "md":
        sigs = markdown_helper.get_block_signatures(content)
    else:
        sigs = js_helper.get_block_signatures(content)

    return block_helpers.get_block_infos_from_signatures(content, sigs)


def _expand_with_parent_offsets(block_infos: list[dict], selected_offsets: list) -> list:
    offset_map = {bi["offset"]: bi for bi in block_infos}
    results: dict = {o: True for o in selected_offsets}

    for offset in selected_offsets:
        if offset in offset_map:
            for parent_offset in offset_map[offset].get("parentOffsets", []):
                results[parent_offset] = True

    return list(results.keys())


def _get_deleted_ranges(block_infos: list[dict], selected_offsets: list) -> list[list]:
    selected_set = set(selected_offsets)
    return [
        [bi["offset"], bi["endPos"]]
        for bi in block_infos
        if bi["offset"] not in selected_set
    ]


def _delete_content_ranges(content: str, deleted_ranges: list[list]) -> str:
    if not deleted_ranges:
        return content

    deleted_ranges.sort(key=lambda r: r[0])
    merged = _merge_ranges(deleted_ranges)

    result = ""
    last_end = 0
    for start, end in merged:
        result += content[last_end:start]
        last_end = end
    result += content[last_end:]
    return result


def _merge_ranges(ranges: list[list]) -> list[list]:
    merged: list[list] = []
    current = list(ranges[0])

    for r in ranges[1:]:
        if r[0] <= current[1]:
            current[1] = max(current[1], r[1])
        else:
            merged.append(current)
            current = list(r)
    merged.append(current)
    return merged


def _cleanup_content(ext: str, content: str) -> str:
    if ext == "php":
        return php_helper.cleanup_content(content)
    if ext == "md":
        return markdown_helper.cleanup_content(content)
    return js_helper.cleanup_content(content)


def _count_occurrences(haystack: str, pattern: str, case_sensitive: bool, use_regex: bool) -> tuple[int, list[int]]:
    if not pattern:
        return 0, []

    indices: list[int] = []

    if use_regex:
        flags = 0 if case_sensitive else re.IGNORECASE
        try:
            for m in re.finditer(pattern, haystack, flags):
                indices.append(m.start())
        except re.error:
            pass
        return len(indices), indices

    # Literal UTF-8-safe search
    import re
    needle = pattern if case_sensitive else pattern.lower()
    text = haystack if case_sensitive else haystack.lower()
    pos = 0
    nlen = len(needle)
    if nlen == 0:
        return 0, []

    while True:
        p = text.find(needle, pos)
        if p == -1:
            break
        indices.append(p)
        pos = p + nlen

    return len(indices), indices


def _replace_all(
    subject: str,
    pattern: str,
    replacement: str,
    case_sensitive: bool,
    use_regex: bool,
) -> tuple[str, int]:
    import re
    if not pattern:
        return subject, 0

    if use_regex:
        flags = 0 if case_sensitive else re.IGNORECASE
        try:
            result, count = re.subn(pattern, replacement, subject, flags=flags)
            return result, count
        except re.error:
            raise ValueError("Invalid regex pattern")

    # Literal multibyte-safe
    needle = pattern if case_sensitive else pattern.lower()
    text = subject if case_sensitive else subject.lower()
    nlen = len(needle)
    count = 0
    result = ""
    pos = 0

    while True:
        p = text.find(needle, pos)
        if p == -1:
            break
        result += subject[pos:p] + replacement
        pos = p + nlen
        count += 1

    result += subject[pos:]
    return result, count


def _trim_preview(line: str) -> str:
    line = line.strip()
    if len(line) > 140:
        return line[:140] + "…"
    return line


# Import re at module level for use in nested helpers
import re  # noqa: E402  (after function defs that reference it inline)
