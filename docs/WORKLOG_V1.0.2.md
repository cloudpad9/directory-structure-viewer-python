# WORKLOG — dsviewer v1.0.2

**Project:** Directory Structure Viewer — PHP → Python Rewrite  
**Version:** 1.0.2  
**Session date:** 2026-03-17  
**Status:** ✅ All 7 phases complete · 128/128 tests passing

---

## 1. Problem Statement

### Background

This session covers the rewrite of `directory-structure-viewer` from PHP + Nginx to Python (FastAPI). The PHP codebase (~1860 LOC in `api.php`) was ported to Python across 7 phases according to the spec. At the start of this session, the code existed but had never been installed or run.

### Issues Addressed This Session

1. **Build system broken** — `pyproject.toml` used `build-backend = "setuptools.backends.legacy:build"`, an API that does not exist in current setuptools, causing `pip install -e .` to fail entirely.

2. **5 unit tests failing** — After manually installing dependencies, the test suite ran but reported 5/128 failures:
   - `test_simple_function_block` — `block_helpers.get_block_content_function` returned wrong content (starting from `)` instead of `{`)
   - `test_default_dispatches_to_function` — same root cause
   - `test_search_regex` — `UnboundLocalError: cannot access local variable 're'`
   - `test_list_content_blocks_md` — Markdown block detection crash with `RuntimeError: Unmatched braces`
   - `test_detects_const_function` — JS helper missing the `const x = function(...)` pattern

3. **Lazy imports in `auth.py`** — `bcrypt` and `fastapi.Request` were wrapped in try/except ImportError blocks; reverted to direct imports after dependencies were installed.

4. **3 gaps vs. spec** — Discovered during a full spec cross-check after tests passed:
   - Missing CORS middleware (spec §9.1)
   - `list_files` did not sort output (spec §13.1)
   - `install.sh` only added PATH to the current shell; spec requires adding to both `.bashrc` and `.zshrc`

---

## 2. Root Cause Analysis

### Bugs 1 & 2 — `get_block_content_function` wrong start position

**PHP original:**
```php
return substr($content, $startPos, $i - $startPos + 1);
```
In PHP, `$startPos` is passed as the position of the first `{` (calculated by the helper functions).

**Python port:** The regex patterns in `js_helper` and `php_helper` return the offset of the full match — typically the portion before `{`, such as `function foo()`. `get_block_content_function` started scanning from `start_pos` and returned `content[start_pos : closing+1]`, causing the result to include `) ` or whitespace before `{`.

**Cascading effect:** `end_pos = offset + len(block_content)` in `get_block_infos_from_signatures` was also computed incorrectly because `block_content` no longer started at `offset`.

### Bug 3 — `UnboundLocalError: re`

`import re` was placed lazily inside the `else` branch (literal search) of `_count_occurrences`, but `re.finditer`, `re.IGNORECASE`, and `re.error` were used in the `if use_regex:` branch above. Python 3.12 raised an error because the variable `re` existed in local scope (due to the lazy import) but had not been assigned when the `if` branch executed first.

### Bug 4 — Markdown using brace matching

`_get_block_infos` called `block_helpers.get_block_infos_from_signatures` for Markdown files, causing `get_block_content_function` to search for `{` in headings like `## Section One` — which never succeeds — resulting in `RuntimeError`.

Markdown uses a **heading-extent model** (a block spans until the next heading at the same level), not brace matching. Both modules have separate extractors, but `_get_block_infos` did not distinguish between them.

### Bug 5 — Missing `CONST_FUNCTION` pattern

The PHP `JavascriptHelper::PATTERNS` defines 5 patterns. The Python port was missing handling for `const multiply = function(x, y) { ... }` — this form does not match `CONST_ARROW` (no `=>`) and does not match `FUNCTION` (no leading `function` keyword).

---

## 3. Solutions & Approaches

### Fix 1 & 2 — `get_block_content_function` + `end_pos`

Added a `brace_start` variable to track the position of the first `{` encountered. Return `content[brace_start : closing+1]` instead of `content[start_pos : closing+1]`.

To fix `end_pos`, used `content.find(block_content, offset)` to locate the actual position of the block in the content, rather than assuming it starts at `offset`:

```python
actual_start = content.find(block_content, offset)
end_pos = actual_start + len(block_content)
```

### Fix 3 — Top-level `import re`

Moved all lazy `import re` statements inside functions up to the top-level imports of `file_processor.py`. Removed 3 lazy import occurrences and the trailing `# noqa: E402` comment.

### Fix 4 — Separate Markdown block extraction

Created a dedicated `_get_markdown_block_infos(content)` function that calls `markdown_helper._get_block_content_from_signature` (heading-extent model) instead of routing through `block_helpers.get_block_infos_from_signatures` (brace-based). `_get_block_infos` now dispatches by extension:

```python
if ext == "md":
    return _get_markdown_block_infos(content)  # heading-extent model
else:
    return block_helpers.get_block_infos_from_signatures(content, sigs)
```

### Fix 5 — Add `CONST_FUNCTION` pattern

```python
"CONST_FUNCTION": re.compile(
    r"\b(?:export\s+)?(?:const|let|var)\s+([a-zA-Z_$][0-9a-zA-Z_$]*)\s*=\s*(?:async\s+)?function\s*\("
),
```

The pattern is placed after `CONST_ARROW` and before `FUNCTION` so that deduplication by line number works correctly.

### Fix 6 — CORS Middleware

Added to `server.py`:
```python
from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
```

### Fix 7 — `list_files` sorting

```python
dirnames[:] = sorted(d for d in dirnames if d not in _EXCLUDE_DIRS)
for fname in sorted(filenames):
```

`os.walk` does not guarantee a consistent order across operating systems — sorting ensures the frontend always receives file lists in alphabetical order.

### Fix 8 — `install.sh` PATH

Changed from logic based on `$SHELL` (updating only one file) to a loop over both:
```bash
for RC_FILE in "$HOME/.bashrc" "$HOME/.zshrc"; do
    if [ -f "$RC_FILE" ] && ! grep -q "dsviewer" "$RC_FILE"; then
        echo "export PATH=\"\$HOME/.dsviewer/bin:\$PATH\"" >> "$RC_FILE"
    fi
done
```

---

## 4. Completed Work

### Build & Infrastructure

- [x] Fix `pyproject.toml`: `setuptools.backends.legacy:build` → `setuptools.build_meta`
- [x] Successfully installed dependencies: `fastapi`, `uvicorn`, `bcrypt`, `python-multipart`, `pytest`, `httpx`
- [x] `pip install -e .` working
- [x] `dsviewer --help` working

### Code Fixes

| File | Changes |
|------|---------|
| `auth.py` | Reverted lazy imports: `import bcrypt as _bcrypt_lib` + `from fastapi import Request` |
| `block_helpers.py` | `get_block_content_function` scans to `{` before returning; fixed `end_pos` calculation |
| `file_processor.py` | Top-level `import re`; extracted `_get_markdown_block_infos()`; sorted output in `list_files` |
| `js_helper.py` | Added `CONST_FUNCTION` pattern |
| `server.py` | Added `CORSMiddleware` |
| `install.sh` | Fixed PATH update: loop over both `.bashrc` and `.zshrc` |

### Test Results

```
128 passed in ~8s
```

| Test file | Tests |
|-----------|------:|
| `test_auth.py` | 11 |
| `test_block_helpers.py` | 15 |
| `test_file_processor.py` | 35 |
| `test_js_helper.py` | 13 |
| `test_markdown_helper.py` | 10 |
| `test_php_helper.py` | 10 |
| `test_simplified_content.py` | 34 |
| **Total** | **128** |

### Codebase Snapshot

```
src/dsviewer/
├── __init__.py              1 LOC
├── __main__.py              4 LOC
├── api.py                 209 LOC   — 13 actions + GET endpoint
├── auth.py                209 LOC   — login, sessions, bcrypt, no-auth mode
├── block_helpers.py       141 LOC   — brace/tag matching, block info
├── cli.py                  64 LOC   — argparse entry point
├── config.py               67 LOC   — AppConfig dataclass
├── file_processor.py      522 LOC   — file ops, search, replace, download, blocks
├── js_helper.py            97 LOC   — JS/Vue block detection (6 patterns)
├── markdown_helper.py      61 LOC   — heading-extent block extraction
├── php_helper.py           46 LOC   — PHP function detection
├── simplified_content.py  626 LOC   — JS outline generator (mask→scan→render)
├── utils.py                42 LOC   — offset_to_line_number, cleanup helpers
├── scripts/
│   └── change_password.py  61 LOC
└── static/
    └── index.html        4285 LOC   — Vue 3 SPA (all 20 api.php → /api patches)

Tests:  7 files · 128 test cases
Config: pyproject.toml · install.sh (123 lines) · README.md
Total Python LOC: ~2258
```

---

## 5. Remaining / Future Work

### P0 — Required before deployment

- [ ] **End-to-end smoke test on a real machine** — Server runs stably in the sandbox, but the full flow has not been tested: login → browse → view → edit → save → download
- [ ] **Update version** in `pyproject.toml` and `__init__.py` from `1.0.0` → `1.0.2` (or appropriate version before git tag)
- [ ] **Push to GitHub** so `install.sh` can download from a real URL (`curl | bash` install)
- [ ] **Test `install.sh`** on a clean Linux machine — has not been run in a real environment

### P1 — Recommended improvements

- [ ] **API integration tests** — only unit tests exist currently. Tests using `httpx.TestClient` are needed to cover full request/response cycles for each action, especially:
  - `download_files` (binary response + ZIP)
  - `get_raw_content` (GET endpoint, token validation)
  - `generate_public_links` → `get_raw_content` flow
  - Auth flow: login → protected action → logout
- [ ] **`change_password` in frontend** — this action exists in the PHP backend but has no UI in the frontend. Currently only accessible via the `dsviewer --change-password` CLI. Consider adding a UI if needed
- [ ] **Test `--change-password` interactive mode** — `scripts/change_password.py` has no tests
- [ ] **`utils.py` — `offset_to_line_number` edge case**: The function currently uses `content.strip()[:offset]` — if `offset` exceeds `len(content.strip())`, the result is silently wrong. Bounds check needed

### P2 — Nice to have

- [ ] **Logging** — server currently uses `log_level="warning"`, errors are not logged. Consider adding structured logging for production use
- [ ] **`tokens.json` cleanup** — `save_tokens` auto-cleans tokens older than 30 days, but no test cases cover this edge case
- [ ] **Concurrent write safety** — `threading.Lock` is used for JSON writes, but no stress tests exist for concurrent requests
- [ ] **Windows support** — path separators and `os.walk` behavior differ on Windows. The spec targets Linux + macOS, but Python tools are often used on Windows as well
- [ ] **`get_file_contents` block filter** — the parent offset expansion logic is complex and only has smoke tests. Additional test cases are needed for nested block scenarios (3+ levels deep)
- [ ] **Binary file detection** — `get_file_content` currently returns an empty string for binary files (because `errors="replace"` masks the error). Consider returning an `is_binary: true` flag so the frontend can render appropriately
- [ ] **Systemd service file** — README mentions systemd but no sample `.service` file exists in the repo

### P3 — Technical debt

- [ ] **Unused `StaticFiles` import** in `server.py` — `StaticFiles` is imported but not used (there is a `pass` comment in the code)
- [ ] **`python-multipart` dependency** — listed in `pyproject.toml` and `install.sh` but no form upload exists in the codebase. Consider removing to reduce dependency footprint
- [ ] **`block_helpers.get_block_contents_from_signatures` vs `_get_markdown_block_infos`** — the two code paths duplicate some `parentOffsets` logic. Consider refactoring into a shared utility if additional languages need to be supported

---

## 6. Fidelity Notes (Key Porting Decisions)

Key decisions that differ from the PHP original, recorded here to avoid future confusion:

| Item | PHP behavior | Python port | Reason |
|------|-------------|-------------|--------|
| `offset_to_line_number` | `substr_count(substr(trim($content), 0, $offset), "\n") + 1` | `content.strip()[:offset].count("\n") + 1` | Faithful port — trim entire content before slicing |
| `js_helper` deduplication | Same-line matches: keep smallest offset | Preserved | Faithful port of `removeDuplicates` |
| `JavascriptHelper` vs `SimplifiedContentHelper` | `class` pattern not in `JavascriptHelper::PATTERNS` | `js_helper.py` has no class pattern | Class detection only in `simplified_content.py::jsEarliestMatch` |
| No-auth mode | N/A (PHP always required auth) | Login returns `{"token": "no-auth", "expires_at": 9999999999}` | Frontend works without modification |
| Session cleanup | Unclear | Expired entries cleaned on every `load_sessions()` call | Prevents unbounded file growth |
| Rate limiting | Present (5 attempts, 15-min lockout) | **Removed** | Spec §4 decision — personal/team tool |

---

*End of WORKLOG_V1.0.2.md*
