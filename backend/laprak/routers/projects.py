from __future__ import annotations

import shutil
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import select

from ..deps import DB, CurrentUser, OwnedProject, Store
from ..models import Build, Draft, Evidence, Project, Section, SourceDocument, Step, Template
from ..service import blockers, bump, project_dir, sections_of, snapshot

router = APIRouter(prefix="/projects", tags=["projects"])


class ProjectIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    language: str = "id"
    identity: dict[str, Any] = Field(default_factory=dict)


class ProjectPatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    language: str | None = None
    identity: dict[str, Any] | None = None
    ai_profile_id: str | None = None
    sections_reviewed: bool | None = None


@router.get("")
def list_projects(user: CurrentUser, session: DB):
    rows = session.exec(select(Project).where(Project.user_id == user.id).order_by(Project.updated_at.desc()))
    return [p.model_dump(mode="json") for p in rows]


@router.post("", status_code=201)
def create_project(body: ProjectIn, user: CurrentUser, session: DB):
    if body.language not in ("id", "en"):
        raise HTTPException(422, "Bahasa harus id atau en.")
    project = Project(user_id=user.id, title=body.title, language=body.language, identity=body.identity)
    session.add(project)
    session.commit()
    session.refresh(project)
    return project.model_dump(mode="json")


@router.get("/{project_id}")
def get_project(project: OwnedProject, session: DB, storage: Store):
    return snapshot(session, project, storage)


@router.patch("/{project_id}")
def patch_project(body: ProjectPatch, project: OwnedProject, session: DB, storage: Store):
    changes = body.model_dump(exclude_unset=True)
    if "language" in changes and changes["language"] not in ("id", "en"):
        raise HTTPException(422, "Bahasa harus id atau en.")
    for key, value in changes.items():
        setattr(project, key, value)
    if {"identity", "language"} & set(changes):
        project.sections_reviewed = False
    bump(session, project)
    session.commit()
    return snapshot(session, project, storage)


@router.delete("/{project_id}", status_code=204)
def delete_project(project: OwnedProject, session: DB, storage: Store):
    for model in (Draft, Build, Evidence, Step, Section, SourceDocument, Template):
        for row in session.exec(select(model).where(model.project_id == project.id)):
            session.delete(row)
    session.delete(project)
    session.commit()
    shutil.rmtree(project_dir(storage, project), ignore_errors=True)


@router.get("/{project_id}/blockers")
def get_blockers(project: OwnedProject, session: DB):
    return blockers(session, project)


class SectionPatch(BaseModel):
    title: str | None = None
    content: str | None = None
    reviewed: bool | None = None
    revision: int | None = None


@router.get("/{project_id}/sections")
def list_sections(project: OwnedProject, session: DB):
    return [s.model_dump(mode="json") for s in sections_of(session, project.id)]


@router.patch("/{project_id}/sections/{section_id}")
def patch_section(section_id: str, body: SectionPatch, project: OwnedProject, session: DB):
    section = session.get(Section, section_id)
    if not section or section.project_id != project.id:
        raise HTTPException(404, "Bagian tidak ditemukan.")
    changes = body.model_dump(exclude_unset=True)
    reviewed = changes.pop("reviewed", None)
    revision = changes.pop("revision", None)
    if any(getattr(section, k) != v for k, v in changes.items()):
        for key, value in changes.items():
            setattr(section, key, value)
        section.revision += 1
        section.reviewed = False
        project.sections_reviewed = False
    if reviewed is not None:
        if reviewed and revision is not None and revision != section.revision:
            raise HTTPException(409, "Bagian berubah sejak ditinjau. Muat ulang lalu periksa kembali.")
        section.reviewed = reviewed
        if not reviewed:
            project.sections_reviewed = False
    bump(session, project)
    session.add(section)
    session.commit()
    session.refresh(section)
    return section.model_dump(mode="json")
