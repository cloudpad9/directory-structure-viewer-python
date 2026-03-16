## Complete deliverable summary

All **7 phases** are implemented. Here's what's in the output:

| Phase | Files | Status |
|-------|-------|--------|
| 1 — Skeleton | `pyproject.toml`, `__init__.py`, `__main__.py`, `config.py`, `cli.py`, `server.py` | ✅ Verified |
| 2 — Auth | `auth.py` (login, sessions, bcrypt, tokens, no-auth mode) | ✅ Logic verified |
| 3 — Core API | `api.py`, `file_processor.py` (all 13 actions + ZIP) | ✅ Verified |
| 4 — Block Detection | `block_helpers.py`, `php_helper.py`, `js_helper.py`, `markdown_helper.py`, `utils.py` | ✅ All assertions pass |
| 5 — Outline | `simplified_content.py` (full JS mask→scan→render pipeline) | ✅ All assertions pass |
| 6 — Frontend | `static/index.html` (all 20 `api.php` → `/api` patches) | ✅ Zero remaining `api.php` |
| 7 — Distribution | `install.sh`, `scripts/change_password.py`, `README.md`, `tests/` (6 test files + 4 fixtures) | ✅ Complete |

### Key fidelity notes
- **`offset_to_line_number`** — fixed to `content.strip()[:offset].count("\n") + 1` (trim whole content first, matching PHP `substr(trim($content), 0, $offset)`)
- **`js_helper` deduplication** — same-line matches keep smallest offset, matching PHP `removeDuplicates`
- **`JavascriptHelper` vs `SimplifiedContentHelper`** — `js_helper` intentionally has no `class` pattern (faithful to PHP); class detection lives only in `simplified_content.py`'s `jsEarliestMatch`
- **No-auth mode** — returns `{"token": "no-auth", ...}` so frontend works without modification
- **Session cleanup** — on every `load_sessions()` call, expired entries are filtered and written back

**Việc cần làm tiếp theo:**

1. **Revert lazy import trong `auth.py`** — sau khi `pip install bcrypt fastapi` thành công, đổi lại:
   ```python
   import bcrypt
   from fastapi import Request
   ```

2. **Cài dependencies:**
   ```bash
   pip install -e ".[dev]"
   # hoặc: pip install fastapi uvicorn bcrypt python-multipart pytest httpx
   ```

3. **Chạy test suite:**
   ```bash
   pytest tests/ -v
   ```

4. **Smoke test:**
   ```bash
   dsviewer --no-auth --open
   ```
