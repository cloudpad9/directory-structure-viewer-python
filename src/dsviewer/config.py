from __future__ import annotations

import json
import threading
from dataclasses import dataclass, field
from pathlib import Path

# Module-level lock shared across all JSON writes
_file_lock = threading.Lock()


def safe_write_json(path: Path, data: dict) -> None:
    """Write JSON to path atomically (thread-safe)."""
    with _file_lock:
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _bcrypt_hash(password: str) -> str:
    import bcrypt  # local import so config can be imported without bcrypt at test time
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


@dataclass
class AppConfig:
    host: str = "0.0.0.0"
    port: int = 9876
    data_dir: Path = field(default_factory=lambda: Path.home() / ".dsviewer" / "data")
    no_auth: bool = False
    open_browser: bool = False

    # ------------------------------------------------------------------
    # Derived paths
    # ------------------------------------------------------------------

    @property
    def users_file(self) -> Path:
        return self.data_dir / "users.json"

    @property
    def sessions_file(self) -> Path:
        return self.data_dir / "sessions.json"

    @property
    def tokens_file(self) -> Path:
        return self.data_dir / "tokens.json"

    # ------------------------------------------------------------------
    # Bootstrap
    # ------------------------------------------------------------------

    def ensure_data_dir(self) -> None:
        """Create data directory and default files if they don't exist."""
        self.data_dir.mkdir(parents=True, exist_ok=True)

        if not self.users_file.exists():
            default_users = {
                "admin": {
                    "password": _bcrypt_hash("admin123")
                }
            }
            safe_write_json(self.users_file, default_users)

        if not self.sessions_file.exists():
            safe_write_json(self.sessions_file, {})

        if not self.tokens_file.exists():
            safe_write_json(self.tokens_file, {})
