"""
cli.py — CLI argument parsing and main entry point.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dsviewer import __version__
from dsviewer.config import AppConfig


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="dsviewer",
        description="Directory Structure Viewer — browse, search, and edit code across repos",
    )
    p.add_argument("--host", default="0.0.0.0", help="Bind address (default: 0.0.0.0)")
    p.add_argument("--port", type=int, default=9876, help="Port number (default: 9876)")
    p.add_argument(
        "--data-dir",
        type=Path,
        default=Path.home() / ".dsviewer" / "data",
        metavar="PATH",
        help="Data directory (default: ~/.dsviewer/data)",
    )
    p.add_argument("--no-auth", action="store_true", help="Disable authentication")
    p.add_argument("--open", action="store_true", dest="open_browser", help="Open browser on start")
    p.add_argument("--version", action="version", version=f"dsviewer {__version__}")
    p.add_argument(
        "--change-password",
        action="store_true",
        help="Interactive: change password for a user",
    )
    return p


def main(argv: list[str] | None = None) -> None:
    parser = _build_parser()
    args = parser.parse_args(argv)

    config = AppConfig(
        host=args.host,
        port=args.port,
        data_dir=args.data_dir,
        no_auth=args.no_auth,
        open_browser=args.open_browser,
    )

    if args.change_password:
        from dsviewer.scripts.change_password import run_interactive
        config.ensure_data_dir()
        from dsviewer import auth as _auth
        _auth.set_config(config)
        run_interactive()
        return

    from dsviewer.server import run
    run(config)


if __name__ == "__main__":
    main()
