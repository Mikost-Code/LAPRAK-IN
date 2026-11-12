from __future__ import annotations

import base64
import os
import secrets
from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration. Every value can be set with a LAPRAK_ environment variable."""

    model_config = SettingsConfigDict(env_prefix="LAPRAK_", env_file=".env", extra="ignore")

    data_dir: Path = Path("data")
    database_url: str = ""
    secret_key: str = ""
    master_key: str = ""
    frontend_origin: str = "http://localhost:5173"
    public_url: str = "http://localhost:8000"
    google_client_id: str = ""
    google_client_secret: str = ""
    dev_login: bool = False
    cookie_secure: bool = False
    session_max_age: int = 60 * 60 * 24 * 14
    tex_compiler: str = ""
    tex_engine: str = "xelatex"
    build_timeout: int = 180
    max_upload_mb: int = 50

    @field_validator("data_dir")
    @classmethod
    def _absolute(cls, value: Path) -> Path:
        return value.resolve()

    def ensure(self) -> "Settings":
        self.data_dir.mkdir(parents=True, exist_ok=True)
        if not self.database_url:
            self.database_url = "sqlite:///" + (self.data_dir / "laprak.sqlite").as_posix()
        self.secret_key = self.secret_key or self._persisted("session.key", lambda: secrets.token_urlsafe(48))
        self.master_key = self.master_key or self._persisted("master.key", lambda: base64.b64encode(os.urandom(32)).decode())
        if len(base64.b64decode(self.master_key)) != 32:
            raise ValueError("LAPRAK_MASTER_KEY harus 32 byte dalam base64.")
        return self

    def _persisted(self, name: str, make) -> str:
        """Development fallback: keep generated keys in data_dir so restarts keep sessions and secrets readable."""
        path = self.data_dir / name
        if path.is_file():
            return path.read_text(encoding="utf-8").strip()
        value = make()
        path.write_text(value, encoding="utf-8")
        try:
            path.chmod(0o600)
        except OSError:
            pass
        return value

    @property
    def master_key_bytes(self) -> bytes:
        return base64.b64decode(self.master_key)


@lru_cache
def get_settings() -> Settings:
    return Settings().ensure()
