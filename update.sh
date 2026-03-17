#!/usr/bin/env bash
# update.sh — Directory Structure Viewer updater
# Usage: curl -fsSL https://raw.githubusercontent.com/cloudpad9/directory-structure-viewer-python/main/update.sh | bash
#    or: dsviewer --update

set -euo pipefail

INSTALL_DIR="$HOME/.dsviewer"
REPO_URL="https://github.com/cloudpad9/directory-structure-viewer-python"
ARCHIVE_URL="${REPO_URL}/archive/refs/heads/main.tar.gz"
VENV_DIR="$INSTALL_DIR/venv"
SERVICE_NAME="dsviewer"

# ── Helpers ────────────────────────────────────────────────────────────────

info() { echo "  [dsviewer] $*"; }
warn() { echo "  [dsviewer] WARNING: $*" >&2; }
die()  { echo "  [dsviewer] ERROR: $*" >&2; exit 1; }

# ── Pre-flight ─────────────────────────────────────────────────────────────

[ -d "$INSTALL_DIR" ] || die "dsviewer is not installed. Run install.sh first."
[ -d "$VENV_DIR"    ] || die "Virtual environment not found. Run install.sh first."

# Lấy version hiện tại trước khi update
CURRENT_VERSION=$("$VENV_DIR/bin/python" -c \
    "from dsviewer import __version__; print(__version__)" 2>/dev/null || echo "unknown")
info "Current version: $CURRENT_VERSION"

# ── Download ───────────────────────────────────────────────────────────────

info "Downloading latest version..."
TMP_DIR=$(mktemp -d)
trap 'rm -rf "$TMP_DIR"' EXIT

curl -fsSL "$ARCHIVE_URL" -o "$TMP_DIR/dsviewer.tar.gz"
tar -xzf "$TMP_DIR/dsviewer.tar.gz" -C "$TMP_DIR"
SRC_DIR=$(find "$TMP_DIR" -maxdepth 1 -type d -name "directory-structure-viewer-python-*" | head -1)
[ -d "$SRC_DIR" ] || die "Failed to extract archive"

# ── Stop service (nếu đang chạy) ──────────────────────────────────────────

SERVICE_WAS_RUNNING=false
if systemctl is-active --quiet "$SERVICE_NAME" 2>/dev/null; then
    info "Stopping $SERVICE_NAME service..."
    sudo systemctl stop "$SERVICE_NAME"
    SERVICE_WAS_RUNNING=true
fi

# ── Replace source code (giữ nguyên data/) ────────────────────────────────

info "Replacing source code..."
rm -rf "$INSTALL_DIR/src"
cp -r "$SRC_DIR/." "$INSTALL_DIR/src_tmp"
mv "$INSTALL_DIR/src_tmp" "$INSTALL_DIR/src"

# ── Update Python dependencies nếu có thay đổi ────────────────────────────

info "Updating dependencies..."
"$VENV_DIR/bin/pip" install --quiet --upgrade \
    "fastapi>=0.104.0" \
    "uvicorn[standard]>=0.24.0" \
    "bcrypt>=4.0.0" \
    "python-multipart>=0.0.6"

# Re-install package (editable mode, nhanh vì chỉ update metadata)
"$VENV_DIR/bin/pip" install --quiet -e "$INSTALL_DIR/src"

# ── Lấy version mới ───────────────────────────────────────────────────────

NEW_VERSION=$("$VENV_DIR/bin/python" -c \
    "from dsviewer import __version__; print(__version__)" 2>/dev/null || echo "unknown")

# ── Restart service ────────────────────────────────────────────────────────

if [ "$SERVICE_WAS_RUNNING" = true ]; then
    info "Restarting $SERVICE_NAME service..."
    sudo systemctl start "$SERVICE_NAME"
    sleep 1
    if systemctl is-active --quiet "$SERVICE_NAME"; then
        info "Service restarted successfully"
    else
        warn "Service failed to restart — check: journalctl -u $SERVICE_NAME -n 20"
    fi
fi

# ── Done ──────────────────────────────────────────────────────────────────

echo ""
echo "  ✓ dsviewer updated: $CURRENT_VERSION → $NEW_VERSION"
if [ "$SERVICE_WAS_RUNNING" = false ]; then
    echo ""
    echo "  Service was not running. Start it with:"
    echo "    sudo systemctl start dsviewer"
fi
echo ""
