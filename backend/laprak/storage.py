"""File storage behind one small interface so a local folder can later be swapped for S3."""
from __future__ import annotations

import hashlib
import shutil
from pathlib import Path
from typing import BinaryIO

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def inside(root: Path, relative: str) -> Path:
    target = (root / relative).resolve()
    if not target.is_relative_to(root.resolve()):
        raise ValueError("Path harus berada di dalam folder yang diizinkan.")
    return target


class LocalStorage:
    def __init__(self, root: Path, secret: str):
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.signer = URLSafeTimedSerializer(secret, salt="laprak-file")

    def project_root(self, user_id: str, project_id: str) -> Path:
        path = self.root / "users" / user_id / "projects" / project_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def relative(self, user_id: str, project_id: str, *parts: str) -> str:
        return "/".join(("users", user_id, "projects", project_id, *parts))

    def path(self, relative: str) -> Path:
        return inside(self.root, relative)

    def save(self, relative: str, stream: BinaryIO, limit: int | None = None) -> Path:
        target = self.path(relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        written = 0
        with target.open("wb") as out:
            while chunk := stream.read(1024 * 1024):
                written += len(chunk)
                if limit and written > limit:
                    out.close()
                    target.unlink(missing_ok=True)
                    raise ValueError("Berkas melebihi batas ukuran unggahan.")
                out.write(chunk)
        return target

    def delete(self, relative: str) -> None:
        target = self.path(relative)
        if target.is_dir():
            shutil.rmtree(target, ignore_errors=True)
        else:
            target.unlink(missing_ok=True)

    def sign(self, relative: str, user_id: str) -> str:
        return self.signer.dumps({"p": relative, "u": user_id})

    def verify(self, token: str, max_age: int = 900) -> tuple[str, str]:
        try:
            data = self.signer.loads(token, max_age=max_age)
        except SignatureExpired as error:
            raise PermissionError("Tautan berkas kedaluwarsa.") from error
        except BadSignature as error:
            raise PermissionError("Tautan berkas tidak valid.") from error
        return data["p"], data["u"]
