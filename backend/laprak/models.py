from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import JSON, Column, Text
from sqlmodel import Field, SQLModel


def uid() -> str:
    return uuid.uuid4().hex


def now() -> datetime:
    return datetime.now(timezone.utc)


def json_field(default_factory):
    return Field(default_factory=default_factory, sa_column=Column(JSON, nullable=False))


class User(SQLModel, table=True):
    id: str = Field(default_factory=uid, primary_key=True)
    google_sub: str = Field(index=True, unique=True)
    email: str = Field(index=True)
    name: str = ""
    picture: str = ""
    locale: str = "id"
    data_key_wrapped: str = ""
    created_at: datetime = Field(default_factory=now)


class AIProfile(SQLModel, table=True):
    id: str = Field(default_factory=uid, primary_key=True)
    user_id: str = Field(foreign_key="user.id", index=True)
    name: str = "9Router"
    base_url: str = "http://localhost:20128/v1"
    text_model: str = ""
    vision_model: str = ""
    structured_mode: str = "json_object"  # json_object | json_schema | prompt
    api_key_enc: str = ""
    vision_ok: bool = False
    text_ok: bool = False
    tested_at: datetime | None = None
    created_at: datetime = Field(default_factory=now)


class Project(SQLModel, table=True):
    id: str = Field(default_factory=uid, primary_key=True)
    user_id: str = Field(foreign_key="user.id", index=True)
    title: str
    language: str = "id"
    identity: dict[str, Any] = json_field(dict)
    template_id: str | None = None
    ai_profile_id: str | None = None
    revision: int = 0
    sections_reviewed: bool = False
    created_at: datetime = Field(default_factory=now)
    updated_at: datetime = Field(default_factory=now)


class SourceDocument(SQLModel, table=True):
    id: str = Field(default_factory=uid, primary_key=True)
    project_id: str = Field(foreign_key="project.id", index=True)
    filename: str
    path: str
    kind: str = "pdf"
    pages: list[dict[str, Any]] = json_field(list)
    outline: dict[str, Any] = json_field(dict)
    reviewed: bool = False
    created_at: datetime = Field(default_factory=now)


class Template(SQLModel, table=True):
    id: str = Field(default_factory=uid, primary_key=True)
    project_id: str = Field(foreign_key="project.id", index=True)
    kind: str = "latex"  # latex | docx_converted
    name: str = ""
    engine: str = "xelatex"
    root: str = ""
    main_path: str = "main.tex"
    slot_map: dict[str, Any] = json_field(dict)
    font_map: dict[str, Any] = json_field(dict)
    status: str = "uploaded"  # uploaded | mapped | verified | failed
    message: str = ""
    created_at: datetime = Field(default_factory=now)


class Step(SQLModel, table=True):
    id: str = Field(default_factory=uid, primary_key=True)
    project_id: str = Field(foreign_key="project.id", index=True)
    position: int = 0
    title: str
    instruction: str = Field(default="", sa_column=Column(Text, nullable=False))
    notes: str = Field(default="", sa_column=Column(Text, nullable=False))
    narrative: str = Field(default="", sa_column=Column(Text, nullable=False))
    facts: list[dict[str, Any]] = json_field(list)
    result: str = "unknown"
    not_applicable: str = ""
    source_ref: dict[str, Any] = json_field(dict)
    reviewed: bool = False
    revision: int = 0
    updated_at: datetime = Field(default_factory=now)


class Evidence(SQLModel, table=True):
    id: str = Field(default_factory=uid, primary_key=True)
    project_id: str = Field(foreign_key="project.id", index=True)
    step_id: str | None = Field(default=None, foreign_key="step.id", index=True)
    position: int = 0
    path: str
    name: str
    hash: str = Field(index=True)
    width: int = 0
    height: int = 0
    captured_at: datetime | None = None
    caption: str = ""
    facts: list[dict[str, Any]] = json_field(list)
    match: dict[str, Any] = json_field(dict)
    created_at: datetime = Field(default_factory=now)


class Section(SQLModel, table=True):
    id: str = Field(default_factory=uid, primary_key=True)
    project_id: str = Field(foreign_key="project.id", index=True)
    key: str
    title: str
    position: int = 0
    content: str = Field(default="", sa_column=Column(Text, nullable=False))
    reviewed: bool = False
    revision: int = 0


class Draft(SQLModel, table=True):
    id: str = Field(default_factory=uid, primary_key=True)
    project_id: str = Field(foreign_key="project.id", index=True)
    operation: str
    target_kind: str  # step | section | evidence | project | document
    target_id: str = ""
    target_revision: int = 0
    content: dict[str, Any] = json_field(dict)
    applied: bool = False
    created_at: datetime = Field(default_factory=now)


class Build(SQLModel, table=True):
    id: str = Field(default_factory=uid, primary_key=True)
    project_id: str = Field(foreign_key="project.id", index=True)
    revision: int = 0
    status: str = "queued"  # queued | running | done | failed
    pdf_path: str = ""
    workspace: str = ""
    log: str = Field(default="", sa_column=Column(Text, nullable=False))
    error: str = ""
    final: bool = False
    created_at: datetime = Field(default_factory=now)
    finished_at: datetime | None = None
