# Dev Setup Guide

This guide walks you through cloning the repo, installing dependencies, running the test suite, and manually testing all features in the browser.

## Requirements

- Git
- Python 3.9+
- pip

---

## Step 1 — Clone the repository

```bash
git clone https://github.com/cloudpad9/directory-structure-viewer-python.git
cd directory-structure-viewer-python
```

---

## Step 2 — Create a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate  # macOS / Linux
# .venv\Scripts\activate   # Windows
```

---

## Step 3 — Install dependencies

```bash
pip install -e ".[dev]"
```

This installs the package in editable mode along with all runtime and dev dependencies (`fastapi`, `uvicorn`, `bcrypt`, `python-multipart`, `pytest`, `httpx`).

---

## Step 4 — Run the test suite

```bash
pytest tests/ -v
```

Expected output — **128 passed**:

```
tests/test_auth.py::test_hash_and_verify PASSED
tests/test_auth.py::test_login_success PASSED
...
128 passed in ~8s
```

To run a specific test file:

```bash
pytest tests/test_block_helpers.py -v
pytest tests/test_file_processor.py -v
```

---

## Step 5 — Start the server

### No-auth mode (recommended for local development)

```bash
dsviewer --no-auth --open
```

The `--open` flag opens the browser automatically. If it doesn't open, navigate to:

```
http://localhost:9876
```

### Authenticated mode

```bash
dsviewer
```

Open http://localhost:9876 — a login dialog will appear. Use the default credentials:

```
Username: admin
Password: admin123
```

### Other options

```bash
# Use a different port if 9876 is already taken
dsviewer --no-auth --port 8080 --open

# Run without opening the browser
dsviewer --no-auth

# See all available options
dsviewer --help
```

If the `dsviewer` command is not found, run it directly with:

```bash
python -m dsviewer --no-auth --open
```

---

## Step 6 — Test in the browser

Work through the following flows in order to verify all features.

### 6.1 Browse a directory

1. Type a directory path into the **Path** input — e.g. `/home/youruser/directory-structure-viewer-python`
2. Click **Analyze**
3. The left pane should populate with a list of files and directories

### 6.2 View file content

1. Check one or two `.py` or `.js` files in the left pane
2. Click **View**
3. The right pane should show the merged content of the selected files

### 6.3 Outline view

1. Check one `.js`, `.php`, or `.vue` file
2. Click **Outline**
3. The right pane should show only function/class signatures — no implementation body

### 6.4 List content blocks

1. In the middle pane, click the dropdown arrow next to a file name → select **List**
2. A list of functions/methods detected in that file should expand
3. Check individual blocks → click **View** to fetch only those blocks

### 6.5 Search

1. Check a few files in the middle pane
2. Type a keyword into the **Search** field → click Search
3. The right pane should show matched lines with a preview for each match

### 6.6 Replace

1. Type the search term into **Search** and the replacement into **Replace**
2. Click Replace
3. The right pane should show a summary: number of files changed and total replacements made

### 6.7 Edit and save

1. Click the dropdown next to a file → select **Edit**
2. The Ace Editor opens with syntax highlighting
3. Make a small change → press `Ctrl+S`
4. A success toast notification should appear

### 6.8 Rename and delete

1. Click the dropdown → **Rename** → enter a new filename → confirm
2. The file should appear under its new name in the list
3. Click the dropdown → **Delete** → confirm in the dialog
4. The file should be removed from the list

### 6.9 Download

1. Check multiple files → click **Download**
2. Single file: downloads directly with the correct MIME type
3. Multiple files: downloads a `.zip` archive containing all selected files

---

## Step 7 — Change password

To change the admin password interactively:

```bash
dsviewer --change-password
```

Follow the prompts in the terminal. After changing, restart the server and verify login works with the new password.

---

## Step 8 — Test install.sh (optional)

It is recommended to test this on a clean machine or VM to avoid affecting your current environment.

```bash
# Check bash syntax without executing
bash -n install.sh

# Run the installer — creates ~/.dsviewer/
bash install.sh
```

After installation, open a new terminal and run:

```bash
dsviewer --no-auth --open
```

To uninstall:

```bash
rm -rf ~/.dsviewer
# Remove the PATH line from ~/.bashrc and/or ~/.zshrc
```

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| `ModuleNotFoundError: bcrypt` | Dependencies not installed | Run `pip install -e ".[dev]"` |
| `Address already in use` on port 9876 | Another process is using the port | Run `lsof -i :9876` and kill the PID, or use `--port 8080` |
| Login dialog persists after correct credentials | API call is failing | Open DevTools (F12) → Network tab → inspect the `/api` response |
| Analyze returns no files | Path doesn't exist or is not readable | Try a path like `/tmp` or your home directory |
| `dsviewer: command not found` | Entry point not on PATH | Use `python -m dsviewer --no-auth` instead |
| Outline returns empty content | File has no detectable functions or classes | Try with a `.js` or `.vue` file that contains at least one function |
| Changes not saved after Ctrl+S | File is not writable | Check file permissions with `ls -l <file>` |
