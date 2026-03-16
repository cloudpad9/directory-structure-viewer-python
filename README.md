# Directory Structure Viewer (Python)

Browse, search, and edit code across multiple repositories from a single web UI — no web server or PHP required.

```
curl -fsSL https://raw.githubusercontent.com/cloudpad9/directory-structure-viewer-python/main/install.sh | bash
```

Then:

```bash
dsviewer                        # start on port 9876
dsviewer --port 8080 --open     # custom port, open browser
dsviewer --no-auth              # skip login (trusted networks only)
```

Default login: **admin / admin123** — change it immediately:

```bash
dsviewer --change-password
```

---

## Features

| Feature | Notes |
|---------|-------|
| Multi-repo browsing | Type any filesystem path in the UI; switch freely between projects |
| File tree + filters | Keyword filter with `-exclusion` syntax |
| View / Outline | Full content or code-structure outline (functions, classes, methods) |
| Block-level selection | Expand a file to pick individual functions; View only those blocks |
| Ace Editor | In-browser syntax-highlighted editing with Ctrl+S save |
| Search | Literal or regex, case-sensitive toggle, character-offset results |
| Replace | Dry-run preview before writing, multibyte UTF-8 safe |
| Download | Single file (correct MIME) or multi-file ZIP |
| Public links | 8-char token links served without login |
| Rename / Delete | Inline file management |
| Dark mode | Persisted in localStorage |
| Named file lists | Save/load sets of selected files (localStorage) |

---

## Installation

### Requirements

- Python 3.9+
- `curl`, `tar`

### 1-liner

```bash
curl -fsSL https://raw.githubusercontent.com/cloudpad9/directory-structure-viewer-python/main/install.sh | bash
```

The installer:
1. Creates `~/.dsviewer/` with a Python virtual environment
2. Installs `fastapi`, `uvicorn`, `bcrypt`, `python-multipart`
3. Symlinks `dsviewer` to `/usr/local/bin/` (falls back to `~/.dsviewer/bin/`)
4. Creates `~/.dsviewer/data/` with default `admin:admin123` credentials

### Manual (development)

```bash
git clone https://github.com/cloudpad9/directory-structure-viewer-python
cd directory-structure-viewer-python
pip install -e ".[dev]"
dsviewer
```

---

## CLI Options

```
dsviewer [OPTIONS]

  --host HOST          Bind address       (default: 0.0.0.0)
  --port PORT          Port number        (default: 9876)
  --data-dir PATH      Data directory     (default: ~/.dsviewer/data)
  --no-auth            Disable login      (trusted networks only)
  --open               Open browser on start
  --version            Show version
  --change-password    Interactive password change
```

---

## Data Directory

```
~/.dsviewer/
├── venv/                # Python virtual environment
├── data/
│   ├── users.json       # { "admin": { "password": "$2b$12$..." } }
│   ├── sessions.json    # Active login sessions (auto-purge expired)
│   └── tokens.json      # Public link tokens (auto-purge after 30 days)
└── bin/
    └── dsviewer         # Wrapper → venv/bin/dsviewer
```

---

## API

All operations go through a single endpoint:

```
POST /api    { "action": "...", ...params }
GET  /api?action=get_raw_content&token=<token>
```

| Action | Auth | Description |
|--------|------|-------------|
| `login` | No | Returns Bearer token |
| `logout` | No | Invalidates token |
| `list_files` | Yes | Recursive directory listing |
| `get_file_content` | Yes | Read single file |
| `save_file_content` | Yes | Write single file |
| `get_file_contents` | Yes | Read multiple files, optional block filtering |
| `get_file_contents_outline` | Yes | Code outline for multiple files |
| `list_content_blocks` | Yes | Detect functions/classes/headings in a file |
| `search_in_files` | Yes | Literal or regex search across files |
| `replace_in_files` | Yes | Literal or regex replace (supports dry-run) |
| `rename_file` | Yes | Rename a file |
| `delete_file` | Yes | Delete a file |
| `download_files` | Yes | Binary download (single file or ZIP) |
| `generate_public_links` | Yes | Create short-token public URLs |
| `get_raw_content` | No* | Serve file by short token |
| `change_password` | Yes | Change authenticated user's password |

*Token is the auth.

---

## Running as a systemd Service

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
sudo systemctl status dsviewer
```

---

## Development

```bash
pip install -e ".[dev]"

# Run tests
pytest tests/ -v

# Run with auto-reload
uvicorn "dsviewer.server:create_app" --factory --reload --port 9876
```

### Project layout

```
src/dsviewer/
├── __init__.py          # Version
├── __main__.py          # python -m dsviewer
├── cli.py               # argparse entry point
├── server.py            # FastAPI app factory + uvicorn launcher
├── config.py            # AppConfig dataclass, data directory bootstrap
├── auth.py              # Login, sessions, bcrypt passwords
├── api.py               # POST /api dispatcher
├── file_processor.py    # All file operations
├── block_helpers.py     # Brace-matched block extraction
├── php_helper.py        # PHP function signature detection
├── js_helper.py         # JS/Vue signature detection
├── markdown_helper.py   # Markdown heading-block extraction
├── simplified_content.py # JS outline generator (mask→scan→render)
├── utils.py             # Shared utilities
├── static/index.html    # Vue 3 SPA (patched from PHP version)
└── scripts/
    └── change_password.py
```

---

## Architecture

```
Browser (Vue 3 SPA)
    │  POST /api  { action, ...params }
    ▼
FastAPI (uvicorn)
    │
    ├── auth.py          bcrypt verify → sessions.json
    ├── file_processor.py  os.walk, read/write, zip, search/replace
    ├── block_helpers.py   brace counting
    ├── {php,js,markdown}_helper.py  regex signature extraction
    └── simplified_content.py  JS mask → scan → render outline
```

No database. No web server. Sessions and tokens stored as JSON files in `~/.dsviewer/data/`.

---

## License

MIT
