from __future__ import annotations

from authlib.integrations.starlette_client import OAuth, OAuthError
from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlmodel import select

from ..config import get_settings
from ..crypto import new_wrapped_data_key
from ..deps import COOKIE, Config, CurrentUser, DB, session_serializer
from ..models import User

router = APIRouter(prefix="/auth", tags=["auth"])
oauth = OAuth()
_registered = False


def google():
    global _registered
    settings = get_settings()
    if not _registered:
        if not settings.google_client_id:
            raise HTTPException(503, "Login Google belum dikonfigurasi di server.")
        oauth.register("google", client_id=settings.google_client_id, client_secret=settings.google_client_secret,
                       server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
                       client_kwargs={"scope": "openid email profile", "code_challenge_method": "S256"})
        _registered = True
    return oauth.google


def upsert_user(session, sub: str, email: str, name: str = "", picture: str = "") -> User:
    user = session.exec(select(User).where(User.google_sub == sub)).first()
    if not user:
        user = User(google_sub=sub, email=email, name=name, picture=picture)
        user.data_key_wrapped = new_wrapped_data_key(get_settings().master_key_bytes, user.id)
        session.add(user)
    else:
        user.email, user.name, user.picture = email, name or user.name, picture or user.picture
    session.commit()
    session.refresh(user)
    return user


def set_cookie(response: Response, user: User, settings) -> None:
    token = session_serializer(settings).dumps({"uid": user.id})
    response.set_cookie(COOKIE, token, max_age=settings.session_max_age, httponly=True, samesite="lax",
                        secure=settings.cookie_secure, path="/")


class Me(BaseModel):
    id: str
    email: str
    name: str
    picture: str
    locale: str


@router.get("/login")
async def login(request: Request, settings: Config):
    redirect = settings.public_url.rstrip("/") + "/api/auth/callback"
    return await google().authorize_redirect(request, redirect)


@router.get("/callback")
async def callback(request: Request, session: DB, settings: Config):
    try:
        token = await google().authorize_access_token(request)
    except OAuthError as error:
        raise HTTPException(400, f"Login Google gagal: {error.error}") from error
    info = token.get("userinfo") or await google().userinfo(token=token)
    if not info.get("email_verified", True):
        raise HTTPException(403, "Email Google belum terverifikasi.")
    user = upsert_user(session, info["sub"], info["email"], info.get("name", ""), info.get("picture", ""))
    response = RedirectResponse(settings.frontend_origin.rstrip("/") + "/")
    set_cookie(response, user, settings)
    return response


class DevLogin(BaseModel):
    email: str
    name: str = "Pengembang"


@router.post("/dev-login", response_model=Me)
def dev_login(body: DevLogin, response: Response, session: DB, settings: Config):
    """Local development only: no Google round-trip. Disabled unless LAPRAK_DEV_LOGIN=1."""
    if not settings.dev_login:
        raise HTTPException(404, "Tidak tersedia.")
    user = upsert_user(session, "dev:" + body.email, body.email, body.name)
    set_cookie(response, user, settings)
    return Me(**user.model_dump())


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(COOKIE, path="/")
    return {"ok": True}


@router.get("/me", response_model=Me)
def me(user: CurrentUser):
    return Me(**user.model_dump())


class LocaleBody(BaseModel):
    locale: str


@router.put("/me/locale", response_model=Me)
def set_locale(body: LocaleBody, user: CurrentUser, session: DB):
    if body.locale not in ("id", "en"):
        raise HTTPException(422, "Bahasa harus id atau en.")
    user.locale = body.locale
    session.add(user)
    session.commit()
    return Me(**user.model_dump())
