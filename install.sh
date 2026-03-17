#!/usr/bin/env bash
# install.sh — Directory Structure Viewer installer
# Usage: curl -fsSL https://raw.githubusercontent.com/cloudpad9/directory-structure-viewer-python/main/install.sh | bash

set -euo pipefail

INSTALL_DIR="$HOME/.dsviewer"
REPO_URL="https://github.com/cloudpad9/directory-structure-viewer-python"
ARCHIVE_URL="${REPO_URL}/archive/refs/heads/main.tar.gz"
BIN_DIR="$INSTALL_DIR/bin"
VENV_DIR="$INSTALL_DIR/venv"
SYSTEM_BIN="/usr/local/bin/dsviewer"

# ── Helpers ────────────────────────────────────────────────────────────────

info()  { echo "  [dsviewer] $*"; }
warn()  { echo "  [dsviewer] WARNING: $*" >&2; }
die()   { echo "  [dsviewer] ERROR: $*" >&2; exit 1; }

need_cmd() {
    command -v "$1" >/dev/null 2>&1 || die "Required command not found: $1"
}

# ── Pre-flight checks ──────────────────────────────────────────────────────

info "Checking requirements..."
need_cmd python3
need_cmd curl
need_cmd tar

PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
PYTHON_MAJOR=$(python3 -c "import sys; print(sys.version_info.major)")
PYTHON_MINOR=$(python3 -c "import sys; print(sys.version_info.minor)")

if [ "$PYTHON_MAJOR" -lt 3 ] || { [ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 9 ]; }; then
    die "Python 3.9+ required (found ${PYTHON_VERSION})"
fi
info "Python ${PYTHON_VERSION} — OK"

# ── Download ───────────────────────────────────────────────────────────────

info "Downloading dsviewer..."
TMP_DIR=$(mktemp -d)
trap 'rm -rf "$TMP_DIR"' EXIT

curl -fsSL "$ARCHIVE_URL" -o "$TMP_DIR/dsviewer.tar.gz"
tar -xzf "$TMP_DIR/dsviewer.tar.gz" -C "$TMP_DIR"
SRC_DIR=$(find "$TMP_DIR" -maxdepth 1 -type d -name "directory-structure-viewer-python-*" | head -1)

[ -d "$SRC_DIR" ] || die "Failed to extract archive"

# ── Install ────────────────────────────────────────────────────────────────

info "Installing to $INSTALL_DIR ..."

# Remove old install (preserve data/)
if [ -d "$INSTALL_DIR" ]; then
    rm -rf "$INSTALL_DIR/venv" "$INSTALL_DIR/bin" "$INSTALL_DIR/src"
fi

mkdir -p "$INSTALL_DIR" "$BIN_DIR" "$INSTALL_DIR/data"

# Copy source
cp -r "$SRC_DIR/." "$INSTALL_DIR/src_tmp"
mv "$INSTALL_DIR/src_tmp" "$INSTALL_DIR/src" 2>/dev/null || true

# ── Virtual environment ────────────────────────────────────────────────────

info "Creating virtual environment..."
python3 -m venv "$VENV_DIR"
"$VENV_DIR/bin/pip" install --quiet --upgrade pip

info "Installing Python dependencies..."
"$VENV_DIR/bin/pip" install --quiet \
    "fastapi>=0.104.0" \
    "uvicorn[standard]>=0.24.0" \
    "bcrypt>=4.0.0" \
    "python-multipart>=0.0.6"

# Install the package itself in editable mode
"$VENV_DIR/bin/pip" install --quiet -e "$INSTALL_DIR/src"

# ── Admin credentials ──────────────────────────────────────────────────────

# Chỉ prompt khi chưa có users.json (lần cài đầu tiên)
# Khi update/reinstall, giữ nguyên credentials hiện tại
if [ ! -f "$INSTALL_DIR/data/users.json" ]; then
    echo ""
    echo "  ─────────────────────────────────────────"
    echo "  Create your admin account"
    echo "  ─────────────────────────────────────────"
    echo ""

    # Prompt username
    while true; do
        printf "  Username: "
        read -r ADMIN_USER
        ADMIN_USER=$(echo "$ADMIN_USER" | tr -d '[:space:]')
        if [ -z "$ADMIN_USER" ]; then
            echo "  Username cannot be empty."
        else
            break
        fi
    done

    # Prompt password với confirm
    while true; do
        printf "  Password (min 6 chars): "
        read -rs ADMIN_PASS
        echo ""
        if [ ${#ADMIN_PASS} -lt 6 ]; then
            echo "  Password must be at least 6 characters."
            continue
        fi
        printf "  Confirm password: "
        read -rs ADMIN_PASS_CONFIRM
        echo ""
        if [ "$ADMIN_PASS" != "$ADMIN_PASS_CONFIRM" ]; then
            echo "  Passwords do not match. Try again."
            continue
        fi
        break
    done

    echo ""
    info "Creating admin account..."
    "$VENV_DIR/bin/python" -m dsviewer.scripts.create_user \
        --data-dir "$INSTALL_DIR/data" \
        --username "$ADMIN_USER" \
        --password "$ADMIN_PASS"

    # Xoá biến khỏi memory ngay sau khi dùng
    unset ADMIN_PASS ADMIN_PASS_CONFIRM
    ADMIN_LOGIN="$ADMIN_USER"
else
    info "Existing credentials preserved (users.json already exists)"
    ADMIN_LOGIN="(your existing username)"
fi

# ── Wrapper script ─────────────────────────────────────────────────────────

cat > "$BIN_DIR/dsviewer" << 'EOF'
#!/usr/bin/env bash
exec "$HOME/.dsviewer/venv/bin/dsviewer" "$@"
EOF
chmod +x "$BIN_DIR/dsviewer"

# ── System-wide symlink ────────────────────────────────────────────────────

if [ -w "$(dirname "$SYSTEM_BIN")" ]; then
    ln -sf "$BIN_DIR/dsviewer" "$SYSTEM_BIN"
    info "Symlinked to $SYSTEM_BIN"
else
    warn "Could not write to $(dirname "$SYSTEM_BIN") — add $BIN_DIR to your PATH manually"
fi

# ── Shell PATH hint ────────────────────────────────────────────────────────

# Thêm vào cả .bashrc và .zshrc nếu file tồn tại
for RC_FILE in "$HOME/.bashrc" "$HOME/.zshrc"; do
    if [ -f "$RC_FILE" ] && ! grep -q "dsviewer" "$RC_FILE" 2>/dev/null; then
        echo "" >> "$RC_FILE"
        echo "# dsviewer" >> "$RC_FILE"
        echo "export PATH=\"\$HOME/.dsviewer/bin:\$PATH\"" >> "$RC_FILE"
        info "Added ~/.dsviewer/bin to PATH in $RC_FILE"
    fi
done

# ── Done ──────────────────────────────────────────────────────────────────

echo ""
echo "  ✓ dsviewer installed successfully!"
echo ""
echo "  To start:  dsviewer"
echo "  Options:   dsviewer --port 8080 --no-auth --open"
echo "  Data dir:  ~/.dsviewer/data/"
echo "  Login:     $ADMIN_LOGIN"
echo ""
echo "  (Run 'dsviewer --change-password' to update the password)"
echo ""
