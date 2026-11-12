from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import select

from ..crypto import decrypt_secret, encrypt_secret
from ..deps import DB, Config, CurrentUser, OwnedProfile, user_data_key
from ..models import AIProfile

router = APIRouter(prefix="/ai-profiles", tags=["ai"])
MODES = ("json_object", "json_schema", "prompt")


def validate_base_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise HTTPException(422, "Base URL tidak boleh memuat kredensial, query, atau fragment.")
    local = parsed.hostname in ("localhost", "127.0.0.1", "::1")
    if not parsed.hostname or (parsed.scheme != "https" and not (parsed.scheme == "http" and local)):
        raise HTTPException(422, "Gunakan HTTPS, atau HTTP hanya untuk localhost (9Router).")
    return url.rstrip("/")


class ProfileIn(BaseModel):
    name: str = Field(default="9Router", max_length=80)
    base_url: str = "http://localhost:20128/v1"
    text_model: str = ""
    vision_model: str = ""
    structured_mode: str = "json_object"
    api_key: str | None = None


class ProfilePatch(BaseModel):
    name: str | None = Field(default=None, max_length=80)
    base_url: str | None = None
    text_model: str | None = None
    vision_model: str | None = None
    structured_mode: str | None = None
    api_key: str | None = None


class TestResult(BaseModel):
    text_ok: bool
    vision_ok: bool


def public(profile: AIProfile) -> dict:
    data = profile.model_dump(mode="json", exclude={"api_key_enc"})
    data["has_api_key"] = bool(profile.api_key_enc)
    return data


@router.get("")
def list_profiles(user: CurrentUser, session: DB):
    rows = session.exec(select(AIProfile).where(AIProfile.user_id == user.id).order_by(AIProfile.created_at))
    return [public(p) for p in rows]


@router.post("", status_code=201)
def create_profile(body: ProfileIn, user: CurrentUser, session: DB, settings: Config):
    if body.structured_mode not in MODES:
        raise HTTPException(422, "Mode keluaran tidak dikenal.")
    profile = AIProfile(user_id=user.id, name=body.name, base_url=validate_base_url(body.base_url),
                        text_model=body.text_model, vision_model=body.vision_model, structured_mode=body.structured_mode)
    if body.api_key:
        profile.api_key_enc = encrypt_secret(user_data_key(user, settings), body.api_key, profile.id)
    session.add(profile)
    session.commit()
    session.refresh(profile)
    return public(profile)


@router.patch("/{profile_id}")
def patch_profile(body: ProfilePatch, profile: OwnedProfile, user: CurrentUser, session: DB, settings: Config):
    changes = body.model_dump(exclude_unset=True)
    api_key = changes.pop("api_key", None)
    if "base_url" in changes:
        changes["base_url"] = validate_base_url(changes["base_url"])
    if "structured_mode" in changes and changes["structured_mode"] not in MODES:
        raise HTTPException(422, "Mode keluaran tidak dikenal.")
    invalidate = any(getattr(profile, k) != v for k, v in changes.items() if k in ("base_url", "text_model", "vision_model", "structured_mode"))
    for key, value in changes.items():
        setattr(profile, key, value)
    if api_key is not None:
        profile.api_key_enc = encrypt_secret(user_data_key(user, settings), api_key, profile.id)
        invalidate = True
    if invalidate:
        profile.text_ok = profile.vision_ok = False
        profile.tested_at = None
    session.add(profile)
    session.commit()
    session.refresh(profile)
    return public(profile)


@router.delete("/{profile_id}", status_code=204)
def delete_profile(profile: OwnedProfile, session: DB):
    session.delete(profile)
    session.commit()


@router.get("/{profile_id}/secret")
def read_secret(profile: OwnedProfile, user: CurrentUser, settings: Config):
    """Only the browser that will call the provider ever receives the key. Never logged, never in snapshots."""
    try:
        secret = decrypt_secret(user_data_key(user, settings), profile.api_key_enc, profile.id)
    except ValueError as error:
        raise HTTPException(500, str(error)) from error
    return {"api_key": secret}


@router.post("/{profile_id}/test-result")
def record_test(body: TestResult, profile: OwnedProfile, session: DB):
    profile.text_ok, profile.vision_ok = body.text_ok, body.vision_ok
    profile.tested_at = datetime.now(timezone.utc)
    session.add(profile)
    session.commit()
    session.refresh(profile)
    return public(profile)
