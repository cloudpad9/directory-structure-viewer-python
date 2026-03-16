"""
change_password.py — Interactive CLI tool for changing a user's password.

Can be invoked via:
  dsviewer --change-password
  python -m dsviewer.scripts.change_password
"""
from __future__ import annotations

import getpass
import sys


def run_interactive() -> None:
    """Prompt for username and passwords, then update users.json."""
    from dsviewer import auth as _auth

    print("\n=== dsviewer — Change Password ===\n")

    users = _auth.load_users()
    if not users:
        print("No users found. Please check your data directory.")
        sys.exit(1)

    print("Available users:", ", ".join(users.keys()))
    username = input("Username: ").strip()

    if username not in users:
        print(f"Error: user '{username}' not found.")
        sys.exit(1)

    old_password = getpass.getpass("Current password: ")
    new_password = getpass.getpass("New password: ")
    confirm = getpass.getpass("Confirm new password: ")

    if new_password != confirm:
        print("Error: new passwords do not match.")
        sys.exit(1)

    if not new_password:
        print("Error: password cannot be empty.")
        sys.exit(1)

    try:
        _auth.change_password(username, old_password, new_password)
        print(f"\n✓ Password for '{username}' updated successfully.")
    except ValueError as exc:
        print(f"\nError: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    # Stand-alone usage: python -m dsviewer.scripts.change_password
    from pathlib import Path
    from dsviewer.config import AppConfig
    from dsviewer import auth as _auth

    config = AppConfig()
    config.ensure_data_dir()
    _auth.set_config(config)
    run_interactive()
