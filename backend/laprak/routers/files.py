from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from ..deps import Store

router = APIRouter(prefix="/files", tags=["files"])


@router.get("/{token}")
def read_file(token: str, storage: Store):
    """Signed, short-lived link. Works for <img src> and PDF viewers without cookies or custom headers."""
    try:
        relative, _user = storage.verify(token)
        path = storage.path(relative)
    except (PermissionError, ValueError) as error:
        raise HTTPException(403, str(error)) from error
    if not path.is_file():
        raise HTTPException(404, "Berkas tidak ditemukan.")
    return FileResponse(path, headers={"Cache-Control": "private, max-age=600"})
