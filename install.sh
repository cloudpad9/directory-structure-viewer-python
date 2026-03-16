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

SHELL_RC=""
case "$SHELL" in
    */bash) SHELL_RC="$HOME/.bashrc" ;;
    */zsh)  SHELL_RC="$HOME/.zshrc"  ;;
esac

if [ -n "$SHELL_RC" ] && ! grep -q "dsviewer" "$SHELL_RC" 2>/dev/null; then
    echo "" >> "$SHELL_RC"
    echo "# dsviewer" >> "$SHELL_RC"
    echo "export PATH=\"\$HOME/.dsviewer/bin:\$PATH\"" >> "$SHELL_RC"
    info "Added ~/.dsviewer/bin to PATH in $SHELL_RC"
fi

# ── Done ──────────────────────────────────────────────────────────────────

echo ""
echo "  ✓ dsviewer installed successfully!"
echo ""
echo "  To start:  dsviewer"
echo "  Options:   dsviewer --port 8080 --no-auth --open"
echo "  Data dir:  ~/.dsviewer/data/"
echo "  Default login: admin / admin123"
echo ""
echo "  (Run 'dsviewer --change-password' to update the password)"
echo ""
