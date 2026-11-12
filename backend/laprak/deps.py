from __future__ import annotations

from functools import lru_cache
from typing import Annotated

from fastapi import Depends, HTTPException, Request
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from sqlmodel import Session, select

from .config import Settings, get_settings
from .crypto import unwrap_data_key
from .db import get_session
from .models import AIProfile, Project, User
from .storage import LocalStorage

COOKIE = "laprak_session"


@lru_cache
def get_storage() -> LocalStorage:
    settings = get_settings()
    return LocalStorage(settings.data_dir / "files", settings.secret_key)


def session_serializer(settings: Settings) -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(settings.secret_key, salt="laprak-session")


def read_session(request: Request, settings: Settings) -> str | None:
    token = request.cookies.get(COOKIE)
    if not token:
        return None
    try:
        return session_serializer(settings).loads(token, max_age=settings.session_max_age)["uid"]
    except (BadSignature, SignatureExpired, KeyError, TypeError):
        return None


def current_user(request: Request, session: Annotated[Session, Depends(get_session)],
                 settings: Annotated[Settings, Depends(get_settings)]) -> User:
    user_id = read_session(request, settings)
    user = session.get(User, user_id) if user_id else None
    if not user:
        raise HTTPException(401, "Masuk terlebih dahulu.")
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        # Double-submit CSRF: SPA sends the header, browsers never attach it cross-site.
        if request.headers.get("x-laprak-client") != "1":
            raise HTTPException(403, "Permintaan tanpa header klien ditolak.")
    return user


CurrentUser = Annotated[User, Depends(current_user)]
DB = Annotated[Session, Depends(get_session)]
Store = Annotated[LocalStorage, Depends(get_storage)]
Config = Annotated[Settings, Depends(get_settings)]


def owned_project(project_id: str, user: CurrentUser, session: DB) -> Project:
    project = session.get(Project, project_id)
    if not project or project.user_id != user.id:
        raise HTTPException(404, "Proyek tidak ditemukan.")
    return project


OwnedProject = Annotated[Project, Depends(owned_project)]


def owned_profile(profile_id: str, user: CurrentUser, session: DB) -> AIProfile:
    profile = session.get(AIProfile, profile_id)
    if not profile or profile.user_id != user.id:
        raise HTTPException(404, "Profil AI tidak ditemukan.")
    return profile


OwnedProfile = Annotated[AIProfile, Depends(owned_profile)]


def user_data_key(user: User, settings: Settings) -> bytes:
    return unwrap_data_key(settings.master_key_bytes, user.data_key_wrapped, user.id)


def first(session: Session, statement):
    return session.exec(select(*statement) if isinstance(statement, tuple) else statement).first()
