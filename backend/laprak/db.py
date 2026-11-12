from __future__ import annotations

from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import event
from sqlmodel import Session, SQLModel, create_engine

from .config import get_settings


@lru_cache
def get_engine():
    url = get_settings().database_url
    kwargs = {"connect_args": {"check_same_thread": False}} if url.startswith("sqlite") else {"pool_pre_ping": True}
    engine = create_engine(url, **kwargs)
    if url.startswith("sqlite"):
        @event.listens_for(engine, "connect")
        def _pragmas(connection, _record):
            cursor = connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.close()
    return engine


def init_db() -> None:
    from . import models  # noqa: F401  (register tables)
    SQLModel.metadata.create_all(get_engine())


def get_session() -> Iterator[Session]:
    # expire_on_commit=False: rows stay readable (model_dump) after commit without an extra refresh.
    with Session(get_engine(), expire_on_commit=False) as session:
        yield session
