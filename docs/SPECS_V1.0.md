# Directory Structure Viewer — Python Rewrite Specification

## Document Info

- **Project**: Rewrite `directory-structure-viewer` from PHP + Nginx to Python (FastAPI)
- **Goal**: `curl | bash` 1-liner install, no web server needed
- **Source repo (PHP)**: https://github.com/cloudpad9/directory-structure-viewer
- **Target repo (Python)**: https://github.com/cloudpad9/directory-structure-viewer-python
- **Source stack**: PHP 7.4+ backend (`api.php` ~1860 LOC), Vue 3 SPA frontend (`index.html` ~4285 LOC)

---

## 1. Overview & Goals

### 1.1 Current Architecture (PHP)

```
User → Nginx/Apache → PHP (api.php) → Filesystem
                    → index.html (Vue 3 SPA via CDN)
                    → JSON files (users.json, tokens.json, auth_tokens.json)
```

**Pain points:**
- Requires PHP installed on the machine
- Requires web server (Nginx/Apache) configuration
- Manual file permission setup (`chmod 664 *.json`)
- Not distributable as a single package

### 1.2 Target Architecture (Python)

```
User → `curl ... | bash` → installs to ~/.dsviewer/
     → `dsviewer` command  → FastAPI + Uvicorn → Filesystem
                           → Embedded index.html (bundled in package)
                           → JSON files (in ~/.dsviewer/data/)
```

**Goals:**
- **1-liner install**: `curl -fsSL https://raw.githubusercontent.com/cloudpad9/directory-structure-viewer-python/main/install.sh | bash`
- **1-liner run**: `dsviewer` (or `dsviewer --port 8080`)
- **Zero external dependencies**: No web server, no database, no PHP, no pip knowledge needed
- **Runnable as systemd service**
- **Feature-complete port**: ALL existing features preserved, API contract identical

### 1.3 Key Design Note — Unrestricted Multi-Repo Browsing

The original PHP version allows users to browse **any directory** on the filesystem via a text input in the UI. Users type a path (e.g. `/home/user/project-a`), click Analyze, browse files, then type a different path (e.g. `/var/www/project-b`) and Analyze again. The UI keeps a "recent paths" dropdown for quick switching.

**The Python port MUST preserve this behavior exactly.** There is no `--dir` flag, no server-side whitelist, and no path restriction. The backend accepts whatever `path` the frontend sends and lists its contents (subject to OS-level file permissions). Authentication (login/password) is the access control layer — once logged in, the user can browse freely.

### 1.4 Package Name

- Python package name: `dsviewer`
- CLI command: `dsviewer`
- Import name: `dsviewer`
- **Not published to PyPI** — distributed via GitHub + `install.sh`

---

## 2. Project Structure

```
directory-structure-viewer-python/
├── install.sh                  # 1-liner installer (curl | bash)
├── pyproject.toml              # Package metadata, dependencies, entry point
├── README.md
├── LICENSE
├── src/
│   └── dsviewer/
│       ├── __init__.py         # Version string
│       ├── __main__.py         # `python -m dsviewer` support
│       ├── cli.py              # CLI argument parsing (argparse)
│       ├── server.py           # FastAPI app factory + uvicorn launcher
│       ├── config.py           # Configuration & data directory management
│       ├── auth.py             # Authentication (login, sessions, password management)
│       ├── api.py              # API route handlers (FastAPI router)
│       ├── file_processor.py   # File operations (list, read, write, download, search, replace)
│       ├── block_helpers.py    # Code block detection (brace matching, signatures)
│       ├── php_helper.py       # PHP block signature extraction
│       ├── js_helper.py        # JavaScript/Vue block signature extraction
│       ├── markdown_helper.py  # Markdown heading-based block extraction
│       ├── simplified_content.py  # Outline/simplified view generator (JS scanner)
│       ├── static/
│       │   └── index.html      # Frontend SPA (modified from original — see Section 8)
│       └── scripts/
│           └── change_password.py  # CLI tool for password management
└── tests/
    ├── test_auth.py
    ├── test_file_processor.py
    ├── test_block_helpers.py
    ├── test_php_helper.py
    ├── test_js_helper.py
    ├── test_markdown_helper.py
    └── test_simplified_content.py
```

---

## 3. Configuration & Data Management

### 3.1 Installation & Data Directory

Everything lives under `~/.dsviewer/` (created by `install.sh`):

```
~/.dsviewer/
├── venv/                # Python virtual environment (managed by install.sh)
├── data/                # Runtime data (managed by the app)
│   ├── users.json       # User accounts  { "admin": { "password": "$2b$12$..." } }
│   ├── sessions.json    # Active login sessions  { "<token>": { "username": "admin", "expires_at": 170... } }
│   └── tokens.json      # Public link tokens  { "a1b2c3d4": { "path": "/...", "created_at": 170... } }
└── bin/
    └── dsviewer         # Symlink → venv/bin/dsviewer (also symlinked to /usr/local/bin/)
```

### 3.2 CLI Arguments

```
dsviewer [OPTIONS]

Options:
  --host HOST          Bind address (default: 0.0.0.0)
  --port PORT          Port number (default: 9876)
  --data-dir PATH      Data directory (default: ~/.dsviewer/data)
  --no-auth            Disable authentication (for local/trusted use)
  --open               Open browser on start
  --version            Show version and exit
  --change-password    Interactive: change password for a user
```

### 3.3 Config Module (`config.py`)

```python
@dataclass
class AppConfig:
    host: str = "0.0.0.0"
    port: int = 9876
    data_dir: Path = Path.home() / ".dsviewer" / "data"
    no_auth: bool = False
    open_browser: bool = False

    # Derived paths
    @property
    def users_file(self) -> Path:
        return self.data_dir / "users.json"

    @property
    def sessions_file(self) -> Path:
        return self.data_dir / "sessions.json"

    @property
    def tokens_file(self) -> Path:
        return self.data_dir / "tokens.json"

    def ensure_data_dir(self):
        """Create data directory and default files if they don't exist."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        # Auto-create users.json with default admin:admin123 if not exists
        if not self.users_file.exists():
            default_users = {
                "admin": {
                    "password": bcrypt_hash("admin123")
                }
            }
            self.users_file.write_text(json.dumps(default_users, indent=2))
```

---

## 4. Authentication Module (`auth.py`)

Simplified from the PHP version. Removed rate limiting and login attempt tracking — unnecessary for a personal/team developer tool.

### 4.1 Constants

```python
TOKEN_EXPIRY = 7 * 24 * 60 * 60    # 7 days in seconds
```

### 4.2 Password Hashing

Use `bcrypt` library (not passlib):

```python
import bcrypt

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())
```

### 4.3 Data Files

**`users.json`** — only the password hash, nothing else:
```json
{
  "admin": {
    "password": "$2b$12$..."
  }
}
```

**`sessions.json`** — active login sessions, only fields that are actually read:
```json
{
  "a1b2c3d4e5f6...64_hex_chars": {
    "username": "admin",
    "expires_at": 1700604800
  }
}
```
**Cleanup strategy — filter on BOTH load and save:** `load_sessions()` reads the file, drops entries where `expires_at < now`, writes back the cleaned version, then returns. This ensures expired sessions are purged every time any auth operation runs — no separate cleanup job needed, file never grows unbounded.

### 4.4 Functions to Implement

| Function | Behavior |
|----------|----------|
| `load_users() -> dict` | Read users.json, auto-create with default admin if missing |
| `save_users(users: dict)` | Write users.json (thread-safe) |
| `load_sessions() -> dict` | Read sessions.json, **filter out expired entries, write back**, return clean dict. Return `{}` if file missing. |
| `save_sessions(sessions: dict)` | Filter expired entries, then write sessions.json (thread-safe) |
| `login(username, password) -> dict` | Validate credentials, create session, return `{token, username, expires_at}` |
| `authenticate(request) -> dict` | Extract Bearer token from header, validate against sessions, return session data or raise 401 |
| `logout(request)` | Remove session token from sessions.json |
| `change_password(username, old_pass, new_pass)` | Verify old password, hash new one, save |

### 4.5 `--no-auth` Mode

When `--no-auth` is passed:
- Skip all authentication checks
- Don't show login dialog on frontend
- The `/api` endpoint skips `authenticate()` call
- Useful for local development / trusted networks

---

## 5. API Module (`api.py`)

Single FastAPI router. ALL endpoints use `POST /api` with JSON body containing `action` field.

> **CRITICAL**: The API contract must be **100% compatible** with the existing frontend.
> The frontend sends `axios.post('api.php', { action: '...', ...params })`.
> In the Python version, this becomes `POST /api` with the same JSON body.
> Only the URL changes: `api.php` → `/api`

### 5.1 Request/Response Format

**Request** (all actions): `POST /api`
```json
{
  "action": "<action_name>",
  ...additional_fields
}
```

**Response** (success): `200 OK` with JSON body
**Response** (error): JSON with `{"error": "message"}` and appropriate HTTP status

### 5.2 Public Actions (no auth required)

#### `login`
```
Request:  { "action": "login", "username": "admin", "password": "admin123" }
Response: { "success": true, "data": { "token": "abc...", "username": "admin", "expires_at": 1700604800 } }
Error:    { "error": "Invalid credentials" }
```

#### `logout`
```
Request:  { "action": "logout" }
Response: { "success": true }
```

### 5.3 Protected Actions (require auth)

All protected actions require `Authorization: Bearer <token>` header.
On invalid/expired token: return `401 {"error": "Authentication required"}`.

#### `list_files`
```
Request:  { "action": "list_files", "path": "/home/user/project" }
Response: { "files": [ { "path": "/home/user/project/src/main.py", "type": "file" }, { "path": "/home/user/project/src", "type": "directory" } ] }
```

**Behavior:**
- **IMPORTANT: No directory restriction.** The `path` comes directly from the frontend text input. Users can browse ANY directory on the filesystem that the process has read access to. This matches the original PHP behavior — users freely switch between different repos/directories via the UI. There is NO `--dir` CLI flag or server-side path restriction.
- Recursively list all files and directories
- Use `RecursiveIteratorIterator` equivalent (os.walk)
- Exclude directories: `.git`, `.svn`, `vendor`, `node_modules`, `.idea`, `.vscode`, `cache`, `tmp`, `temp`, `logs`, `dist`, `build`, `target`
- Return `SELF_FIRST` order (directories before their children)
- Return empty array if path is not a valid directory

#### `get_file_content`
```
Request:  { "action": "get_file_content", "path": "/path/to/file.py" }
Response: { "content": "file content as string..." }
```

#### `save_file_content`
```
Request:  { "action": "save_file_content", "path": "/path/to/file.py", "content": "new content..." }
Response: { "success": true }
```

#### `get_file_contents`
```
Request:  { "action": "get_file_contents", "paths": ["/path/a.py", "/path/b.js"], "blocks": { "/path/b.js": [42, 108] } }
Response: { "contents": [ { "path": "/path/a.py", "content": "..." }, { "path": "/path/b.js", "content": "...filtered..." } ] }
```

**Behavior:**
- If `blocks` for a path is empty → return full content
- If `blocks` has offsets → keep only those blocks (by offset), delete the rest
- Auto-expand parent blocks (if a child block is selected, its parent container must also be kept)
- After deletion, run cleanup (remove empty blocks, redundant blank lines, etc.)

#### `get_file_contents_outline`
```
Request:  { "action": "get_file_contents_outline", "paths": ["/path/a.js"] }
Response: { "contents": [ { "path": "/path/a.js", "content": "function foo();\nclass Bar {\n  method();\n}" } ] }
```

**Behavior:** For each file, generate a simplified/outline view using `SimplifiedContentHelper` logic (see Section 7).

#### `list_content_blocks`
```
Request:  { "action": "list_content_blocks", "path": "/path/to/file.js" }
Response: { "blocks": [ { "signature": "function foo()", "offset": 42, "endPos": 198, "lineNumber": 5, "parentOffsets": [] }, ... ] }
```

**Behavior:**
- Detect file type by extension
- `.php` → `PhpHelper.get_block_signatures()`
- `.md` → `MarkdownHelper.get_block_signatures()`
- Everything else → `JavascriptHelper.get_block_signatures()`
- Return `BlockHelper.get_block_infos_from_signatures()` result

#### `search_in_files`
```
Request:  { "action": "search_in_files", "paths": [...], "pattern": "TODO", "options": { "case_sensitive": true, "regex": false } }
Response: {
  "summary": { "scanned": 10, "matched_files": 3, "total_matches": 7 },
  "matches": [
    {
      "path": "/path/to/file.py",
      "total": 2,
      "lines": [
        { "line": 15, "occurrences": 1, "indices": [8], "preview": "# TODO: fix this" },
        { "line": 42, "occurrences": 1, "indices": [4], "preview": "    TODO: refactor" }
      ]
    }
  ]
}
```

**Behavior:**
- Scan each file line by line
- Support both literal string search and regex
- Case-sensitive or case-insensitive
- Return character offsets within each line
- Truncate preview to 140 chars

#### `replace_in_files`
```
Request:  { "action": "replace_in_files", "paths": [...], "pattern": "old", "replacement": "new", "options": { "case_sensitive": true, "regex": false, "dry_run": false } }
Response: {
  "summary": { "processed": 10, "changed_files": 3, "total_replaced": 7, "dry_run": false },
  "changed": [ { "path": "/path/to/file.py", "replaced": 2 } ]
}
```

**Behavior:**
- Same pattern matching as search
- If `dry_run: true`, count but don't write
- If `dry_run: false`, write changes to disk
- Multibyte-safe (UTF-8)

#### `rename_file`
```
Request:  { "action": "rename_file", "path": "/path/to/old.py", "new_name": "new.py" }
Response: { "success": true, "new_path": "/path/to/new.py" }
```

**Validations:** No path separators in new_name, target doesn't already exist, file exists and is writable.

#### `delete_file`
```
Request:  { "action": "delete_file", "path": "/path/to/file.py" }
Response: { "success": true }
```

#### `download_files`
```
Request:  { "action": "download_files", "paths": ["/path/to/file.py"] }
Response: Binary file content (single file) or ZIP archive (multiple files)
```

**Behavior:**
- Single file: return with correct MIME type, `Content-Disposition: inline`
- Multiple files: create temporary ZIP, return as `application/zip`
- Use common path prefix for ZIP relative paths

**Response type:** This returns binary data (not JSON). Set appropriate `Content-Type` and `Content-Disposition` headers.

#### `generate_public_links`
```
Request:  { "action": "generate_public_links", "paths": ["/path/to/file.py", "/path/to/file2.js"] }
Response: { "links": [ { "path": "/path/to/file.py", "token": "a1b2c3d4" }, ... ] }
```

**Behavior:**
- Generate 8-char hex token for each file
- Store in `tokens.json`: `{ "a1b2c3d4": { "path": "/path/to/file.py", "created_at": ... } }`
- Auto-cleanup tokens older than 30 days on save

#### `get_raw_content` (Public — no auth)
```
Request:  GET /api?action=get_raw_content&token=a1b2c3d4
Response: Binary file content with correct MIME type
```

**This is the only GET endpoint.** It serves files via short tokens generated by `generate_public_links`. No auth required (the token IS the auth).

#### `change_password`
```
Request:  { "action": "change_password", "old_password": "old", "new_password": "new" }
Response: { "success": true }
```

Uses authenticated user's username from token.

---

## 6. Block Detection Modules

These modules detect code "blocks" (functions, classes, methods, etc.) for the expand/collapse feature.

### 6.1 `block_helpers.py` — Core Block Operations

Port of PHP `BlockHelper` class:

#### `get_block_infos_from_signatures(content, signatures) -> list[dict]`
- Input: `signatures` = list of `[signature_text, offset, line_number, type?]`
- Sort by offset ascending
- For each signature: extract the full block content (brace-matched or tag-matched)
- Compute `endPos = offset + len(block_content)`
- Compute `parentOffsets` = offsets of blocks that fully contain this one
- Return list of `{ signature, offset, endPos, lineNumber, parentOffsets }`

#### `get_block_contents_from_signatures(content, signatures) -> dict[int, str]`
- Return `{ offset: block_content_string }` for each signature

#### `get_block_content(content, signature, offset, type) -> str`
Dispatch by type:
- `"STYLE"` → `get_block_content_style()`: find `</style>` closing tag
- `"APP_DIV"` → `get_block_content_app_div()`: count nested `<div>`/`</div>` tags
- Default → `get_block_content_function()`: brace counting (`{` / `}`) with quote awareness

#### `get_block_content_function(content, signature, start_pos) -> str`
**Critical algorithm — port exactly:**
- Walk character by character from `start_pos`
- Track `brace_count`, `single_quote_count`, `double_quote_count`
- On `{`: increment brace_count (only if not in quotes)
- On `}`: decrement brace_count (only if not in quotes); if brace_count == 0 → return substring
- On `'`: toggle single_quote_count
- On `"`: toggle double_quote_count
- On `\r` or `\n`: reset both quote counts to 0
- If no matching brace found: raise RuntimeError

### 6.2 `php_helper.py`

Port of PHP `PhpHelper` class:

#### `get_block_signatures(content) -> list`
Regex: `\b(?:(?:public|protected|private|static|final|abstract)\s+)*function\s+([a-zA-Z_]\w*)\s*\(`
Return: `[[match_text, offset, line_number], ...]`

#### `cleanup_content(content) -> str`
1. Remove empty blocks (`class Foo { }`)
2. Remove `use` statements
3. Remove comments (multi-line `/* */`, single-line `//`, shell `#`)
4. Remove redundant blank lines

### 6.3 `js_helper.py`

Port of PHP `JavascriptHelper` class:

#### `get_block_signatures(content) -> list`
Apply these regex patterns in order:
```python
PATTERNS = {
    'CONST_ARROW': r'\b(?:(const|let|var)\s+)([a-zA-Z_$][0-9a-zA-Z_$]*)\s*=\s*(?:async\s+)?(?:\(\s*.*?\s*\)\s*=>|([a-zA-Z_$][0-9a-zA-Z_$]*\s*=>))',
    'FUNCTION': r'\b(?:async\s+)?function\s+([a-zA-Z_$][0-9a-zA-Z_$]*)\s*\(',
    'METHOD': r'\b(?:async\s+)?([a-zA-Z_$][0-9a-zA-Z_$]*)\s*\(\s*\)\s*\{',
    'STYLE': r'<style[^>]*>',
    'CONST_OBJECT': r'\b(?:(const|let|var)\s+)([a-zA-Z_$][0-9a-zA-Z_$]*)\s*=\s*\{',
    'APP_DIV': r'<div\s+id="app"'
}
```

**Deduplication:** If multiple patterns match the same line number, keep only the one with the smallest offset.

#### `cleanup_content(content) -> str`
1. Remove empty blocks
2. Remove SVGs (`<svg>...</svg>`)
3. Remove blank code lines (lines that are just `;`)
4. Remove redundant blank lines

### 6.4 `markdown_helper.py`

Port of PHP `MarkdownHelper` + `MarkdownBlockHelper`:

#### `get_block_signatures(content) -> list`
Regex: `^(#{2,3}\s.+)$` (multiline)
Return: `[[heading_text, offset, line_number], ...]`

#### Block content extraction
Each block extends from its heading to the next heading of same or higher level (fewer `#`), or to end of content.

---

## 7. Simplified Content / Outline Generator (`simplified_content.py`)

Port of PHP `SimplifiedContentHelper`. This is the most complex module — a JavaScript-aware parser.

### 7.1 Purpose
Generate a code outline showing only function/class/method signatures — hiding implementation details. Used by the "Outline" view feature.

### 7.2 Core Algorithm

1. **Mask step** (`js_mask`): Create a copy of the source where all strings, comments, template literals, and regex literals are replaced with spaces (preserving newlines for line counting). This lets regex operate on "clean" code.

2. **Scan step** (`js_scan_range`): Recursively scan a range of the masked source to find declarations:
   - Context-aware: different patterns for top-level, class body, object body, and block body
   - Pattern types: `container`, `class`, `function`, `anon`, `assigned`, `classField`, `propAssigned`, `method`
   - For each match: find the matching `}` using the real source (not mask), extract children recursively

3. **Render step** (`render_simplified_outline`): Walk the AST nodes:
   - `class` → print signature + `{` ... render children ... `}`
   - `container` (export default) → same as class
   - function/method in class/object context → print `signature;`
   - function with children outside class → print signature + `{` ... children ... `}`
   - leaf function → print `signature;`

### 7.3 Pattern Details (must port exactly)

Each pattern is a regex that matches a declaration followed by `{`. The patterns are defined in `js_earliest_match()` and selected based on context:

**Top-level context** uses: `container`, `class`, `function`, `assigned`, `anon`
**Class/Object context** uses: `method`, `classField`, `propAssigned`, `function`, `assigned`, `anon`, `class`
**Block context** uses: `function`, `assigned`, `anon`, `class`

### 7.4 Helper Functions

| Function | Purpose |
|----------|---------|
| `js_mask(src)` | Mask strings, comments, templates, regex. Preserve newlines. |
| `js_scan_range(src, mask, start, end, ctx)` | Find declarations in range, return AST nodes |
| `js_earliest_match(mask, offset, ctx)` | Find nearest declaration match for given context |
| `js_is_control_flow_before(mask, brace_pos)` | Check if `{` belongs to if/for/while/etc. |
| `find_matching_brace_js(src, open_pos)` | Find `}` matching `{` at open_pos (string/comment aware) |
| `normalize_assigned_signature(sig)` | Convert `const foo = (a) => {` to `function foo(a)` |
| `looks_like_regex_start(src, pos)` | Heuristic: is `/` a regex literal opener? |
| `render_simplified_outline(nodes, depth, parent_ctx)` | Render AST to outline string |

### 7.5 Signature Normalization

The `normalize_assigned_signature()` must handle all these patterns:
```
const foo = function(a, b)       → function foo(a, b)
const foo = (a, b) =>            → function foo(a, b)
const foo = a =>                 → function foo(a)
export const foo = (a) =>        → function foo(a)
#privateFn = (a) =>              → function privateFn(a)  (class fields)
myProp: function(a, b)           → function myProp(a, b)  (object properties)
myProp: (a) =>                   → function myProp(a)     (object properties)
```

---

## 8. Frontend (`static/index.html`)

### 8.1 Principle: Preserve As-Is

The `index.html` (4285 LOC) is a fully self-contained Vue 3 SPA that loads all dependencies via CDN (Vue 3, Axios, Ace Editor, Google Fonts). It requires NO build step. The Python version copies this file into the package and makes only the minimal URL changes listed below. **All frontend features, components, CSS, and behavior remain untouched.**

### 8.2 Exact Changes Required

**A) Replace all `axios.post('api.php', ...)` → `axios.post('/api', ...)`**

There are 20 occurrences of `axios.post('api.php'` — all are simple string replacements.

**B) Replace the 2 `baseUrl` constructions in the Links dialog:**

The "Public" and "AI" link modes construct a base URL like:
```javascript
// BEFORE (PHP)
const baseUrl = window.location.origin + window.location.pathname.replace(/[^/]*$/, 'api.php');

// AFTER (Python)
const baseUrl = window.location.origin + '/api';
```
These appear at 2 places in the `updateLinksContent()` function.

**That's it — no other changes.**

### 8.3 Complete UI Feature Checklist

Below is every interactive feature in the UI, its mechanism, and its spec coverage. Features marked "Frontend-only" live entirely in the browser (Vue state, localStorage, CSS) and are automatically preserved by keeping `index.html` intact. Features marked "API" require a working backend endpoint.

#### LEFT PANE — Directory Browser

| # | Feature | Mechanism | Spec Coverage |
|---|---------|-----------|---------------|
| 1 | **Path input** with recent paths dropdown | Frontend — `PathInput` component, `recentPaths` stored in localStorage | Frontend-only ✅ |
| 2 | **Delete recent path** (x button in dropdown) | Frontend — `DeleteConfirmDialog`, removes from `recentPaths` array | Frontend-only ✅ |
| 3 | **Analyze** button | API `list_files` | Section 5.3 ✅ |
| 4 | **Filter by keywords** (supports `foo -bar` exclusion syntax) | Frontend — `filteredFiles` computed, tokenizes on whitespace, `-` prefix = exclude | Frontend-only ✅ |
| 5 | **Clear** filter + selection button | Frontend — resets `filterKeyword`, `selectedFiles` | Frontend-only ✅ |
| 6 | **File checkboxes** (individual selection) | Frontend — `v-model="selectedFiles"` | Frontend-only ✅ |
| 7 | **Directory checkboxes** (recursive: selects all children) | Frontend — `toggleDirectorySelection()` adds all files under prefix | Frontend-only ✅ |
| 8 | **Directory Structure** tree preview (bottom of left pane) | Frontend — `renderDirectoryTree()` generates ASCII tree | Frontend-only ✅ |
| 9 | **Resize handle** (drag to resize left pane) | Frontend — `ResizeHandle` component, `leftWidth` persisted | Frontend-only ✅ |

#### MIDDLE PANE — Top Controls Row

| # | Feature | Mechanism | Spec Coverage |
|---|---------|-----------|---------------|
| 10 | **View** button | API `get_file_contents` (with optional block filters) | Section 5.3 ✅ |
| 11 | **Outline** button | API `get_file_contents_outline` | Section 5.3 ✅ |
| 12 | **Check all / Un-check** toggle button | Frontend — `checkAllFiles()` / `clearCheckedFiles()` | Frontend-only ✅ |
| 13 | **Download** button (multi-file) | API `download_files` → returns binary (file or ZIP) | Section 5.3 ✅ |
| 14 | **Dark mode toggle** (🌙/☀️ icon) | Frontend — `toggleDarkMode()`, adds `dark-mode` class to body, persisted in localStorage | Frontend-only ✅ |
| 15 | **Collapse** (← button, 2 levels) | Frontend — `collapseLevel` 0→1 hides left pane, 1→2 hides middle pane | Frontend-only ✅ |
| 16 | **Expand** (click collapsed pane) | Frontend — `expandPanes()` resets `collapseLevel` to 0 | Frontend-only ✅ |
| 17 | **Logout** button | API `logout` | Section 5.2 ✅ |

#### MIDDLE PANE — Search & Replace Row

| # | Feature | Mechanism | Spec Coverage |
|---|---------|-----------|---------------|
| 18 | **Search** input + button | API `search_in_files` on checked files | Section 5.3 ✅ |
| 19 | **Replace** input + button | API `search_in_files` + `replace_in_files` (both called) | Section 5.3 ✅ |

#### MIDDLE PANE — Lists & Actions Row

| # | Feature | Mechanism | Spec Coverage |
|---|---------|-----------|---------------|
| 20 | **Save** button → save selected files as named list | Frontend — `ListPickerDialog`, stored in localStorage under `directory-structure-viewer:lists` | Frontend-only ✅ |
| 21 | **Load** button → load named list of files | Frontend — `ListPickerDialog`, reads from localStorage | Frontend-only ✅ |
| 22 | **Clear** selected files button | Frontend — `clearSelectedFiles()` | Frontend-only ✅ |
| 23 | **Tree** button → show directory tree of selected/checked files | Frontend — `openSelectedTree()` calls `renderDirectoryTree()` → shows in `NotificationViewer` dialog | Frontend-only ✅ |
| 24 | **Links** button → show file paths/URLs dialog | Mixed — 4 modes (see below) | Section 5.3 (partial — see 8.4) |

#### MIDDLE PANE — Selected Files Filter

| # | Feature | Mechanism | Spec Coverage |
|---|---------|-----------|---------------|
| 25 | **Filter selected files** input | Frontend — `middlePaneFilter`, filters `filteredMiddlePaneItems` | Frontend-only ✅ |

#### MIDDLE PANE — Per-File Actions (SplitButton dropdown)

| # | Feature | Mechanism | Spec Coverage |
|---|---------|-----------|---------------|
| 26 | **View** (primary button for text files) | API `get_file_contents` for single file | Section 5.3 ✅ |
| 27 | **Download** (primary button for binary files) | API `download_files` for single file | Section 5.3 ✅ |
| 28 | **List** (expand content blocks) | API `list_content_blocks` → shows block checkboxes | Section 5.3 ✅ |
| 29 | **Outline** (single file) | API `get_file_contents_outline` for single file | Section 5.3 ✅ |
| 30 | **Edit** (opens Ace Editor) | API `get_file_content` to load, `save_file_content` on Ctrl+S | Section 5.3 ✅ |
| 31 | **Rename** → dialog | API `rename_file` | Section 5.3 ✅ |
| 32 | **Delete** → confirm dialog | API `delete_file` | Section 5.3 ✅ |
| 33 | **x** (remove from selected files) | Frontend — `removeSelectedFile()` | Frontend-only ✅ |

#### MIDDLE PANE — Block Selection

| # | Feature | Mechanism | Spec Coverage |
|---|---------|-----------|---------------|
| 34 | **Block checkboxes** (after List expand) | Frontend state — `checkedContentBlocks[file]` = array of offsets | Frontend-only ✅ |
| 35 | **Block-level View** (blocks passed to View/Outline) | API `get_file_contents` with `blocks` param | Section 5.3 ✅ |
| 36 | **Nested block highlighting** (level-0, level-1, level-2 colors) | Frontend CSS — `.block-item.level-N` | Frontend-only ✅ |
| 37 | **Directory checkbox in middle pane** | Frontend — `toggleDirectoryCheckInMiddle()` checks all visible files under dir | Frontend-only ✅ |

#### RIGHT PANE — Content Display

| # | Feature | Mechanism | Spec Coverage |
|---|---------|-----------|---------------|
| 38 | **Merged content** display (contenteditable) | Frontend — `mergeContent` computed joins all `fileContents` | Frontend-only ✅ |
| 39 | **Download** merged content button | Frontend — creates Blob + download link | Frontend-only ✅ |
| 40 | **Copy** merged content button | Frontend — `navigator.clipboard.writeText()` with fallback | Frontend-only ✅ |
| 41 | **Ace Editor** (syntax highlighting, Ctrl+S save) | Frontend CDN — `ace.min.js`, `AceEditor` component | Frontend-only ✅ (save via API `save_file_content`) |
| 42 | **Search results** view (clickable paths, highlighted matches) | Frontend — `SearchResults` component | Frontend-only ✅ (data from API) |
| 43 | **Replace results** view | Frontend — `ReplaceResults` component | Frontend-only ✅ (data from API) |

#### DIALOGS

| # | Feature | Mechanism | Spec Coverage |
|---|---------|-----------|---------------|
| 44 | **Login dialog** (blocks app until login) | API `login` | Section 5.2 ✅ |
| 45 | **Rename dialog** | API `rename_file` | Section 5.3 ✅ |
| 46 | **Delete confirm dialog** (files) | API `delete_file` | Section 5.3 ✅ |
| 47 | **Delete confirm dialog** (recent paths) | Frontend — removes from `recentPaths` array | Frontend-only ✅ |
| 48 | **Links dialog** (4 modes) | Mixed — see 8.4 below | Section 5.3 + frontend ✅ |
| 49 | **List picker dialog** (Save/Load named file lists) | Frontend — localStorage, max 50 lists, 1000 files/list | Frontend-only ✅ |
| 50 | **Notification viewer** (full-screen modal with pre-formatted text) | Frontend — eventBus `notification` event | Frontend-only ✅ |
| 51 | **Toast notifications** (top-right, auto-dismiss) | Frontend — eventBus `toast` event, 2500ms default | Frontend-only ✅ |

#### LAYOUT & RESPONSIVE

| # | Feature | Mechanism | Spec Coverage |
|---|---------|-----------|---------------|
| 52 | **3-pane layout** (left, middle, right) | Frontend CSS | Frontend-only ✅ |
| 53 | **Left pane resize handle** (drag) | Frontend — `ResizeHandle` component | Frontend-only ✅ |
| 54 | **Middle pane resize handle** (drag) | Frontend — `ResizeHandle` component | Frontend-only ✅ |
| 55 | **Mobile responsive** (hamburger menu, overlay, stacked layout) | Frontend — CSS `@media` + `MobileMenuButton` + `MobileOverlay` | Frontend-only ✅ |
| 56 | **State persistence** (survives page refresh) | Frontend — `saveStateToLocalStorage()` on state change, `loadStateFromLocalStorage()` on mount | Frontend-only ✅ |

### 8.4 Links Dialog — 4 Modes Detail

The Links button opens a dialog with 4 radio modes:

| Mode | Behavior | API call? |
|------|----------|-----------|
| **Relative** | Shows file paths relative to base directory (e.g., `src/main.py`) | No — frontend computes via `getRelativePath()` |
| **Full** | Shows absolute file paths (e.g., `/home/user/project/src/main.py`) | No — uses raw paths from state |
| **Public** | Generates short-token URLs for each file, shows full URLs | Yes — `generate_public_links` API, then constructs `{baseUrl}?action=get_raw_content&relpath=...&token=...` |
| **AI** | Generates token list for AI agents, shows path→token mapping + curl instructions | Yes — `generate_public_links` API, then formats as `relpath,token` list |

Both "Public" and "AI" modes construct `baseUrl` from `window.location.origin` — see Section 8.2(B) for the required change.

### 8.5 Serving

FastAPI serves `index.html` at the root route `/`:

```python
from fastapi.responses import FileResponse

@app.get("/")
async def serve_frontend():
    return FileResponse(Path(__file__).parent / "static" / "index.html")
```

The `index.html` loads Vue 3, Axios, and Ace Editor from CDN — no build step needed. The CDN URLs are:
- `https://cdn.jsdelivr.net/npm/vue@3/dist/vue.global.js`
- `https://cdn.jsdelivr.net/npm/axios/dist/axios.min.js`
- `https://cdnjs.cloudflare.com/ajax/libs/ace/1.36.2/ace.min.js`
- `https://fonts.googleapis.com/css2?family=Roboto:wght@400;700&family=Roboto+Mono:wght@400;700&display=swap`

---

## 9. Server Module (`server.py`)

### 9.1 FastAPI App Factory

```python
def create_app(config: AppConfig) -> FastAPI:
    app = FastAPI(title="Directory Structure Viewer")

    # Include API router
    app.include_router(api_router)

    # Serve frontend
    @app.get("/")
    async def index():
        return FileResponse(static_dir / "index.html")

    # CORS (allow all for local tool)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    return app
```

### 9.2 Main Endpoint Structure

```python
@router.post("/api")
async def api_handler(request: Request):
    body = await request.json()
    action = body.get("action", "")

    # Public actions
    if action == "login":
        return handle_login(body)
    if action == "logout":
        return handle_logout(request)

    # Auth check (skip if --no-auth)
    if not config.no_auth:
        user = authenticate(request)
    else:
        user = {"username": "local"}

    # Protected actions
    match action:
        case "list_files": ...
        case "get_file_content": ...
        case "save_file_content": ...
        case "get_file_contents": ...
        case "get_file_contents_outline": ...
        case "download_files": ...
        case "list_content_blocks": ...
        case "search_in_files": ...
        case "replace_in_files": ...
        case "rename_file": ...
        case "delete_file": ...
        case "generate_public_links": ...
        case "change_password": ...
        case _: return {"error": "Invalid action"}

@router.get("/api")
async def api_get_handler(action: str = "", token: str = ""):
    """Handle GET requests — only get_raw_content uses this."""
    if action == "get_raw_content":
        return handle_get_raw_content(token)
    return {"error": "Invalid action"}
```

### 9.3 Uvicorn Launcher

```python
def run_server(config: AppConfig):
    config.ensure_data_dir()
    app = create_app(config)

    if config.open_browser:
        import webbrowser
        webbrowser.open(f"http://localhost:{config.port}")

    uvicorn.run(app, host=config.host, port=config.port, log_level="info")
```

---

## 10. CLI Module (`cli.py`)

### 10.1 Entry Point

```python
def main():
    parser = argparse.ArgumentParser(
        prog="dsviewer",
        description="Directory Structure Viewer — browse repos and extract code context for AI agents"
    )
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=9876)
    parser.add_argument("--data-dir", type=Path, default=Path.home() / ".dsviewer" / "data")
    parser.add_argument("--no-auth", action="store_true", help="Disable authentication")
    parser.add_argument("--open", action="store_true", help="Open browser on start")
    parser.add_argument("--version", action="version", version=f"dsviewer {__version__}")
    parser.add_argument("--change-password", action="store_true", help="Change user password")

    args = parser.parse_args()

    if args.change_password:
        change_password_interactive(args.data_dir)
        return

    config = AppConfig(
        host=args.host,
        port=args.port,
        data_dir=args.data_dir,
        no_auth=args.no_auth,
        open_browser=args.open
    )

    print(f"🚀 DSViewer running at http://{config.host}:{config.port}")
    print(f"📁 Data directory: {config.data_dir}")
    if config.no_auth:
        print("⚠️  Authentication disabled (--no-auth)")

    run_server(config)
```

### 10.2 `__main__.py`

```python
from dsviewer.cli import main
main()
```

This enables `python -m dsviewer`.

---

## 11. Package Configuration (`pyproject.toml`)

```toml
[build-system]
requires = ["setuptools>=68.0", "wheel"]
build-backend = "setuptools.backends._legacy:_Backend"

[project]
name = "dsviewer"
version = "1.0.0"
description = "Browse repos and extract code context for AI agents"
readme = "README.md"
license = {text = "MIT"}
requires-python = ">=3.10"
dependencies = [
    "fastapi>=0.104.0",
    "uvicorn[standard]>=0.24.0",
    "bcrypt>=4.0.0",
]

[project.scripts]
dsviewer = "dsviewer.cli:main"

[tool.setuptools.packages.find]
where = ["src"]

[tool.setuptools.package-data]
dsviewer = ["static/**/*"]
```

### 11.1 Dependencies

| Package | Purpose | Why not stdlib |
|---------|---------|----------------|
| `fastapi` | HTTP framework | Async, auto-docs, clean routing |
| `uvicorn[standard]` | ASGI server | Production-ready, no nginx needed |
| `bcrypt` | Password hashing | PHP `password_hash()` compatible |

**No other dependencies.** Everything else uses Python stdlib:
- `json` for JSON files
- `os`, `pathlib` for filesystem
- `re` for regex
- `secrets` for token generation
- `zipfile` for ZIP creation
- `mimetypes` for MIME detection
- `argparse` for CLI
- `time` for timestamps
- `threading.Lock` for file write safety (replacement for PHP `LOCK_EX`)

### 11.2 Installation Script (`install.sh`)

This is the primary distribution method. User runs:

```bash
curl -fsSL https://raw.githubusercontent.com/cloudpad9/directory-structure-viewer-python/main/install.sh | bash
```

**The script must:**

1. **Check Python ≥ 3.10** — try `python3 --version`, if missing or too old, print clear error and exit
2. **Create `~/.dsviewer/`** directory structure
3. **Create venv** at `~/.dsviewer/venv/` using `python3 -m venv`
4. **Install the package** into venv via `pip install git+https://github.com/cloudpad9/directory-structure-viewer-python.git`
5. **Create symlink** `~/.dsviewer/bin/dsviewer` → `~/.dsviewer/venv/bin/dsviewer`
6. **Add to PATH** — append `export PATH="$HOME/.dsviewer/bin:$PATH"` to `~/.bashrc` and `~/.zshrc` (if they exist), skip if line already present
7. **Print success message** with usage instructions

**Script behavior:**
- Idempotent — safe to run multiple times (updates existing install)
- No `sudo` required (everything in `~/.dsviewer/`)
- Works on Linux and macOS
- Prints each step as it runs (not silent)
- On error: prints clear message and exits with non-zero code

**Example output:**
```
📦 Installing Directory Structure Viewer...
  ✓ Python 3.12.3 found
  ✓ Created ~/.dsviewer/
  ✓ Created virtual environment
  ✓ Installed dsviewer and dependencies
  ✓ Added to PATH

✅ Installation complete!

  Usage:   dsviewer
  Or:      dsviewer --port 8080
  Config:  dsviewer --help

  Open a new terminal or run: source ~/.bashrc
```

**Uninstall:** `rm -rf ~/.dsviewer` and remove the PATH line from shell rc files. Mention this in README.

---

## 12. Download / Binary Response Handling

### 12.1 Single File Download

```python
from fastapi.responses import Response
import mimetypes

def handle_download_single(path: str) -> Response:
    mime = mimetypes.guess_type(path)[0] or "application/octet-stream"
    content = Path(path).read_bytes()
    filename = Path(path).name
    return Response(
        content=content,
        media_type=mime,
        headers={
            "Content-Disposition": f'inline; filename="{filename}"',
            "Content-Length": str(len(content)),
        }
    )
```

### 12.2 Multi-File ZIP Download

```python
import zipfile
import tempfile

def handle_download_multi(paths: list[str]) -> Response:
    # Compute common prefix for relative paths inside ZIP
    base_dir = os.path.commonpath([os.path.dirname(p) for p in paths])

    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
        with zipfile.ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED) as zf:
            for path in paths:
                arcname = os.path.relpath(path, base_dir)
                zf.write(path, arcname)
        tmp_path = tmp.name

    content = Path(tmp_path).read_bytes()
    os.unlink(tmp_path)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return Response(
        content=content,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="downloaded_files_{timestamp}.zip"',
        }
    )
```

---

## 13. File Operations (`file_processor.py`)

### 13.1 `get_files(dir_path: str) -> list[dict]`

```python
EXCLUDE_DIRS = {
    '.git', '.svn', 'vendor', 'node_modules', '.idea', '.vscode',
    'cache', 'tmp', 'temp', 'logs', 'dist', 'build', 'target'
}

def get_files(dir_path: str) -> list[dict]:
    """Recursively list files and directories, excluding common non-essential dirs."""
    results = []
    for root, dirs, files in os.walk(dir_path):
        # Filter excluded directories IN-PLACE to prevent os.walk from descending
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        dirs.sort()  # Consistent ordering

        # Add directory entries
        for d in dirs:
            results.append({"path": os.path.join(root, d), "type": "directory"})

        # Add file entries
        for f in sorted(files):
            results.append({"path": os.path.join(root, f), "type": "file"})

    return results
```

### 13.2 Search Implementation

Must be UTF-8 safe. Use Python's native Unicode string handling.

```python
def count_occurrences(haystack: str, pattern: str, case_sensitive: bool, use_regex: bool) -> tuple[int, list[int]]:
    """Return (count, [char_indices])"""
    if not pattern:
        return 0, []

    indices = []
    if use_regex:
        flags = 0 if case_sensitive else re.IGNORECASE
        for m in re.finditer(pattern, haystack, flags):
            indices.append(m.start())
        return len(indices), indices

    # Literal search
    text = haystack if case_sensitive else haystack.lower()
    needle = pattern if case_sensitive else pattern.lower()
    pos = 0
    while True:
        idx = text.find(needle, pos)
        if idx == -1:
            break
        indices.append(idx)
        pos = idx + len(needle)
    return len(indices), indices
```

### 13.3 Replace Implementation

```python
def replace_all(subject: str, pattern: str, replacement: str, case_sensitive: bool, use_regex: bool) -> tuple[str, int]:
    """Return (new_string, replacement_count)"""
    if not pattern:
        return subject, 0

    if use_regex:
        flags = 0 if case_sensitive else re.IGNORECASE
        result, count = re.subn(pattern, replacement, subject, flags=flags)
        return result, count

    # Literal replace (case-insensitive aware)
    if case_sensitive:
        count = subject.count(pattern)
        return subject.replace(pattern, replacement), count

    # Case-insensitive literal replace
    lower_subject = subject.lower()
    lower_pattern = pattern.lower()
    result = []
    pos = 0
    count = 0
    while True:
        idx = lower_subject.find(lower_pattern, pos)
        if idx == -1:
            result.append(subject[pos:])
            break
        result.append(subject[pos:idx])
        result.append(replacement)
        pos = idx + len(pattern)
        count += 1
    return ''.join(result), count
```

### 13.4 Public Link Token Management

```python
TOKEN_LENGTH = 8  # 8 hex chars = 4 random bytes
TOKEN_MAX_AGE = 30 * 24 * 60 * 60  # 30 days

def generate_short_token(path: str) -> str:
    token = secrets.token_hex(TOKEN_LENGTH // 2)
    tokens = load_tokens()
    tokens[token] = {"path": path, "created_at": int(time.time())}
    save_tokens(tokens)  # auto-cleans old tokens
    return token

def get_path_from_token(token: str) -> str:
    tokens = load_tokens()
    if token not in tokens:
        raise ValueError("Invalid or expired token")
    return tokens[token]["path"]
```

---

## 14. Utility Functions

### 14.1 `offset_to_line_number(content, offset) -> int`
```python
def offset_to_line_number(content: str, offset: int) -> int:
    return content[:offset].strip().count('\n') + 1
```
Note: The PHP version uses `substr(trim($content), 0, $offset)` — it trims the entire content first, then counts newlines in the prefix. Port this exactly.

### 14.2 `remove_redundant_blank_lines(content) -> str`
Collapse consecutive blank lines into single blank lines.

### 14.3 `remove_comments(content) -> str`
Remove multi-line `/* ... */`, single-line `// ...`, and shell-style `# ...` comments using regex.

---

## 15. systemd Service (Documentation Only)

Include in README:

```ini
# /etc/systemd/system/dsviewer.service
[Unit]
Description=Directory Structure Viewer
After=network.target

[Service]
Type=simple
User=youruser
ExecStart=/home/youruser/.dsviewer/bin/dsviewer --port 8080
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now dsviewer
```

---

## 16. Testing Requirements

### 16.1 Test Coverage Priorities

1. **Auth module**: login, session token validation, password change
2. **Block helpers**: brace matching, PHP/JS/Markdown signature detection
3. **Simplified content**: JS masking, outline generation for various code patterns
4. **Search/Replace**: literal, regex, case-insensitive, UTF-8
5. **File listing**: exclude dirs, recursive traversal
6. **API integration**: request/response format for each action

### 16.2 Test Data

Create test fixtures in `tests/fixtures/`:
- `sample.php` — PHP class with methods
- `sample.js` — JS file with functions, arrow functions, classes
- `sample.vue` — Vue SFC with template, script, style
- `sample.md` — Markdown with h2/h3 headings

### 16.3 Test Framework

Use `pytest`. No additional test dependencies beyond `httpx` for FastAPI test client.

```toml
[project.optional-dependencies]
dev = ["pytest>=7.0", "httpx>=0.25.0"]
```

---

## 17. Implementation Order

Recommended order for the agent to implement:

1. **Phase 1 — Skeleton**: `pyproject.toml`, `cli.py`, `server.py`, `config.py`, `__init__.py`, `__main__.py`
   - Goal: `pip install -e .` → `dsviewer` starts and serves a "Hello World" at `/`

2. **Phase 2 — Auth**: `auth.py`
   - Goal: Login/logout/session validation works with JSON files

3. **Phase 3 — Core API**: `api.py`, `file_processor.py`
   - Goal: `list_files`, `get_file_content`, `save_file_content`, `search_in_files`, `replace_in_files`, `rename_file`, `delete_file`, `download_files`, `generate_public_links`, `get_raw_content`

4. **Phase 4 — Block Detection**: `block_helpers.py`, `php_helper.py`, `js_helper.py`, `markdown_helper.py`
   - Goal: `list_content_blocks`, `get_file_contents` (with block filtering)

5. **Phase 5 — Outline**: `simplified_content.py`
   - Goal: `get_file_contents_outline`

6. **Phase 6 — Frontend**: Copy `index.html` → replace `api.php` with `/api`
   - Goal: Full working frontend

7. **Phase 7 — Distribution**: `install.sh`, `change_password.py` script, README, tests, `--no-auth` mode
   - Goal: `curl | bash` install works end-to-end

---

## 18. Critical Implementation Notes

### 18.1 Thread Safety

Use `threading.Lock()` for all JSON file writes. The PHP version uses `LOCK_EX` flag — Python equivalent:

```python
import threading

_file_lock = threading.Lock()

def safe_write_json(path: Path, data: dict):
    with _file_lock:
        path.write_text(json.dumps(data, indent=2))
```

### 18.2 Binary Response

The `download_files` action returns **binary data**, not JSON. The FastAPI handler must detect this and return a `Response` object with appropriate headers instead of a dict.

### 18.3 Regex Porting

PHP regex (PCRE) and Python regex (`re` module) are highly compatible. Key differences to watch:
- PHP `preg_match_all(..., PREG_OFFSET_CAPTURE)` → Python `re.finditer()` with `.start()` for offsets
- PHP `/pattern/m` modifier → Python `re.MULTILINE`
- PHP `/pattern/i` modifier → Python `re.IGNORECASE`
- PHP `/pattern/s` modifier → Python `re.DOTALL`

### 18.4 Path Handling

- Use `os.path` consistently (not `pathlib`) for user-facing file paths since the frontend sends raw string paths
- Use `pathlib.Path` for internal package paths (data dir, static files)
- Never assume path separator — the tool should work on both Linux and macOS

### 18.5 Error Handling

All API errors should return JSON:
```python
@app.exception_handler(Exception)
async def generic_error_handler(request, exc):
    return JSONResponse(
        status_code=getattr(exc, 'status_code', 500),
        content={"error": str(exc)}
    )
```

### 18.6 No-Auth Mode Frontend Signal

When `--no-auth` is active, the server should communicate this to the frontend. Options:
- Add a `GET /api/config` endpoint returning `{"auth_required": false}`
- Or: the frontend's existing auth check will get a 200 (not 401) when no auth is needed — handle this by having the API return success for any request when `--no-auth`

**Recommended approach:** When `--no-auth`, the `login` action should return a hardcoded success response:
```json
{"success": true, "data": {"token": "no-auth", "username": "local", "expires_at": 9999999999}}
```
This way the frontend works without modification — it "logs in" with any credentials and gets a permanent token.

---

## Appendix A: Complete API Action Summary

| Action | Auth | Method | Input Params | Return |
|--------|------|--------|-------------|--------|
| `login` | No | POST | `username`, `password` | `{success, data: {token, username, expires_at}}` |
| `logout` | No | POST | — | `{success: true}` |
| `get_raw_content` | No | GET | `token` (query param) | Binary file |
| `list_files` | Yes | POST | `path` | `{files: [{path, type}]}` |
| `get_file_content` | Yes | POST | `path` | `{content: "..."}` |
| `save_file_content` | Yes | POST | `path`, `content` | `{success: true}` |
| `get_file_contents` | Yes | POST | `paths`, `blocks` | `{contents: [{path, content}]}` |
| `get_file_contents_outline` | Yes | POST | `paths` | `{contents: [{path, content}]}` |
| `download_files` | Yes | POST | `paths` | Binary (file or ZIP) |
| `list_content_blocks` | Yes | POST | `path` | `{blocks: [{signature, offset, endPos, lineNumber, parentOffsets}]}` |
| `search_in_files` | Yes | POST | `paths`, `pattern`, `options` | `{summary, matches}` |
| `replace_in_files` | Yes | POST | `paths`, `pattern`, `replacement`, `options` | `{summary, changed}` |
| `rename_file` | Yes | POST | `path`, `new_name` | `{success, new_path}` |
| `delete_file` | Yes | POST | `path` | `{success: true}` |
| `generate_public_links` | Yes | POST | `paths` | `{links: [{path, token}]}` |
| `change_password` | Yes | POST | `old_password`, `new_password` | `{success: true}` |

---

## Appendix B: Source File Reference Map

| Python Module | Corresponds to PHP |
|--------------|-------------------|
| `auth.py` | `class Auth` in api.php (lines 1-160) — **simplified**: removed rate limiting and login attempt tracking |
| `file_processor.py` | `class FileProcessor` in api.php (lines 420-1100) |
| `block_helpers.py` | `class BlockHelper` in api.php (lines 200-340) |
| `php_helper.py` | `class PhpHelper` in api.php (lines 342-390) |
| `js_helper.py` | `class JavascriptHelper` in api.php (lines 392-510) |
| `markdown_helper.py` | `class MarkdownHelper` + `class MarkdownBlockHelper` in api.php (lines 512-580) |
| `simplified_content.py` | `class SimplifiedContentHelper` in api.php (lines 582-1050) |
| `config.py` | Constants scattered in api.php |
| `api.py` | `FileProcessor::main()` routing in api.php (lines 420-550) |

---

*End of Specification*
