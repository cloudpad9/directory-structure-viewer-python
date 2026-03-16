"""
api.py — FastAPI router.

ALL actions are dispatched through a single POST /api endpoint.
The only GET endpoint is GET /api?action=get_raw_content&token=...
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response

from dsviewer import auth as _auth
from dsviewer import file_processor as fp

if TYPE_CHECKING:
    from dsviewer.config import AppConfig

router = APIRouter()

# Will be set by server.py when building the app
_config: "AppConfig | None" = None


def set_config(config: "AppConfig") -> None:
    global _config
    _config = config


def _no_auth() -> bool:
    return _config is not None and _config.no_auth


# ---------------------------------------------------------------------------
# GET /api — only get_raw_content (public, token-gated)
# ---------------------------------------------------------------------------

@router.get("/api")
async def api_get(request: Request):
    action = request.query_params.get("action", "")

    if action == "get_raw_content":
        token = request.query_params.get("token", "")
        try:
            data, mime, filename = fp.get_raw_content(token)
            return Response(
                content=data,
                media_type=mime,
                headers={
                    "Content-Disposition": f'inline; filename="{filename}"',
                    "Cache-Control": "public, max-age=3600",
                },
            )
        except (ValueError, FileNotFoundError) as exc:
            return JSONResponse(status_code=404, content={"error": str(exc)})

    return JSONResponse(status_code=400, content={"error": "Invalid action for GET"})


# ---------------------------------------------------------------------------
# POST /api — all actions
# ---------------------------------------------------------------------------

@router.post("/api")
async def api_post(request: Request):
    try:
        body = await request.json()
    except Exception:
        body = {}

    action = body.get("action", "")

    # ------------------------------------------------------------------
    # Public actions (no auth)
    # ------------------------------------------------------------------

    if action == "login":
        if _no_auth():
            return JSONResponse({
                "success": True,
                "data": {"token": "no-auth", "username": "local", "expires_at": 9999999999},
            })
        username = body.get("username", "")
        password = body.get("password", "")
        try:
            result = _auth.login(username, password)
            return JSONResponse({"success": True, "data": result})
        except ValueError as exc:
            return JSONResponse(status_code=401, content={"error": str(exc)})

    if action == "logout":
        _auth.logout(request)
        return JSONResponse({"success": True})

    # ------------------------------------------------------------------
    # Authentication gate
    # ------------------------------------------------------------------

    if not _no_auth():
        try:
            session = _auth.authenticate(request)
        except _auth._HTTPException as exc:
            return JSONResponse(status_code=exc.status_code, content={"error": exc.detail})
    else:
        session = {"username": "local"}

    # ------------------------------------------------------------------
    # Protected actions
    # ------------------------------------------------------------------

    try:
        if action == "list_files":
            path = body.get("path", "")
            return JSONResponse({"files": fp.list_files(path)})

        if action == "get_file_content":
            path = body.get("path", "")
            return JSONResponse({"content": fp.get_file_content(path)})

        if action == "save_file_content":
            path = body.get("path", "")
            content = body.get("content", "")
            fp.save_file_content(path, content)
            return JSONResponse({"success": True})

        if action == "get_file_contents":
            paths = body.get("paths", [])
            blocks = body.get("blocks", {})
            return JSONResponse({"contents": fp.get_file_contents(paths, blocks)})

        if action == "get_file_contents_outline":
            paths = body.get("paths", [])
            return JSONResponse({"contents": fp.get_file_contents_outline(paths)})

        if action == "download_files":
            paths = body.get("paths", [])
            # Filter to readable files
            readable = [p for p in paths
                        if isinstance(p, str) and __import__("os").path.isfile(p)
                        and __import__("os").access(p, __import__("os").R_OK)]
            if not readable:
                return JSONResponse(status_code=404, content={"error": "No readable file to download"})

            if len(readable) == 1:
                data, mime, filename = fp.download_single_file(readable[0])
                return Response(
                    content=data,
                    media_type=mime,
                    headers={
                        "Content-Disposition": f'inline; filename="{filename}"',
                        "Cache-Control": "no-cache, must-revalidate",
                        "Expires": "0",
                    },
                )
            else:
                zip_data, zip_name = fp.download_files_as_zip(readable)
                return Response(
                    content=zip_data,
                    media_type="application/zip",
                    headers={
                        "Content-Disposition": f'attachment; filename="{zip_name}"',
                        "Cache-Control": "no-cache, must-revalidate",
                        "Expires": "0",
                    },
                )

        if action == "list_content_blocks":
            path = body.get("path", "")
            return JSONResponse({"blocks": fp.list_content_blocks(path)})

        if action == "search_in_files":
            paths = body.get("paths", [])
            pattern = str(body.get("pattern", ""))
            options = dict(body.get("options", {}))
            return JSONResponse(fp.search_in_files(paths, pattern, options))

        if action == "replace_in_files":
            paths = body.get("paths", [])
            pattern = str(body.get("pattern", ""))
            replacement = str(body.get("replacement", ""))
            options = dict(body.get("options", {}))
            return JSONResponse(fp.replace_in_files(paths, pattern, replacement, options))

        if action == "rename_file":
            path = body.get("path", "")
            new_name = body.get("new_name", "")
            return JSONResponse(fp.rename_file(path, new_name))

        if action == "delete_file":
            path = body.get("path", "")
            return JSONResponse(fp.delete_file(path))

        if action == "generate_public_links":
            paths = body.get("paths", [])
            return JSONResponse({"links": fp.generate_public_links(paths)})

        if action == "change_password":
            old_pw = body.get("old_password", "")
            new_pw = body.get("new_password", "")
            _auth.change_password(session["username"], old_pw, new_pw)
            return JSONResponse({"success": True})

        return JSONResponse(status_code=400, content={"error": "Invalid action"})

    except (ValueError, RuntimeError, OSError) as exc:
        return JSONResponse(status_code=500, content={"error": str(exc)})
    except Exception as exc:
        return JSONResponse(status_code=500, content={"error": str(exc)})
