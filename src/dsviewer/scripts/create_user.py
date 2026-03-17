"""
create_user.py — Tạo hoặc ghi đè user trong users.json.

Dùng bởi install.sh sau khi cài xong để set credentials lần đầu.
Có thể gọi trực tiếp:
  python -m dsviewer.scripts.create_user --username admin --data-dir ~/.dsviewer/data
"""
from __future__ import annotations

import argparse
import getpass
import json
import sys
from pathlib import Path


def _bcrypt_hash(password: str) -> str:
    import bcrypt
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def create_user(data_dir: Path, username: str, password: str) -> None:
    """Tạo hoặc cập nhật user trong users.json."""
    data_dir.mkdir(parents=True, exist_ok=True)
    users_file = data_dir / "users.json"

    # Load users hiện có nếu file đã tồn tại
    if users_file.exists():
        try:
            users = json.loads(users_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            users = {}
    else:
        users = {}

    users[username] = {"password": _bcrypt_hash(password)}
    users_file.write_text(json.dumps(users, indent=2), encoding="utf-8")


def run_interactive(data_dir: Path, username: str | None = None) -> None:
    """Prompt interactively cho username + password."""
    print("\n=== dsviewer — Create Admin User ===\n")

    if not username:
        while True:
            username = input("Username: ").strip()
            if not username:
                print("  Username cannot be empty.")
            elif " " in username:
                print("  Username cannot contain spaces.")
            else:
                break

    while True:
        password = getpass.getpass("Password: ")
        if len(password) < 6:
            print("  Password must be at least 6 characters.")
            continue
        confirm = getpass.getpass("Confirm password: ")
        if password != confirm:
            print("  Passwords do not match. Try again.")
            continue
        break

    create_user(data_dir, username, password)
    print(f"\n  ✓ User '{username}' created successfully.\n")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create or update a dsviewer user account"
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path.home() / ".dsviewer" / "data",
        help="Data directory (default: ~/.dsviewer/data)",
    )
    parser.add_argument("--username", help="Username (prompted if omitted)")
    parser.add_argument("--password", help="Password (prompted if omitted)")

    args = parser.parse_args()

    # Nếu cả username lẫn password được truyền qua args (dùng bởi install.sh)
    if args.username and args.password:
        if len(args.password) < 6:
            print("Error: password must be at least 6 characters.")
            sys.exit(1)
        create_user(args.data_dir, args.username, args.password)
        print(f"  ✓ User '{args.username}' created.")
    else:
        # Interactive mode
        run_interactive(args.data_dir, username=args.username)


if __name__ == "__main__":
    main()
