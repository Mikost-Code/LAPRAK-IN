from __future__ import annotations

import hashlib
import io
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel, Field
from sqlmodel import select

from ..deps import DB, Config, CurrentUser, OwnedProject, Store, owned_project
from ..models import Evidence, Project, Step
from ..service import bump, evidence_of, evidence_url, steps_of, touch_step

router = APIRouter(tags=["steps"])


def owned_step(step_id: str, user: CurrentUser, session: DB) -> tuple[Step, Project]:
    step = session.get(Step, step_id)
    project = session.get(Project, step.project_id) if step else None
    if not step or not project or project.user_id != user.id:
        raise HTTPException(404, "Langkah tidak ditemukan.")
    return step, project


def owned_evidence(evidence_id: str, user: CurrentUser, session: DB) -> tuple[Evidence, Project]:
    item = session.get(Evidence, evidence_id)
    project = session.get(Project, item.project_id) if item else None
    if not item or not project or project.user_id != user.id:
        raise HTTPException(404, "Gambar tidak ditemukan.")
    return item, project


OwnedStep = Annotated[tuple[Step, Project], Depends(owned_step)]
OwnedEvidence = Annotated[tuple[Evidence, Project], Depends(owned_evidence)]


class StepIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    instruction: str = ""
    position: int | None = None
    source_ref: dict[str, Any] = Field(default_factory=dict)


class StepPatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    instruction: str | None = None
    notes: str | None = None
    narrative: str | None = None
    facts: list[dict[str, Any]] | None = None
    result: str | None = None
    not_applicable: str | None = None


class ReviewBody(BaseModel):
    reviewed: bool
    revision: int | None = None


class OrderBody(BaseModel):
    ids: list[str]


def _renumber(rows: list) -> None:
    for position, row in enumerate(rows):
        row.position = position


@router.get("/projects/{project_id}/steps")
def list_steps(project: OwnedProject, session: DB):
    return [s.model_dump(mode="json") for s in steps_of(session, project.id)]


@router.post("/projects/{project_id}/steps", status_code=201)
def create_step(body: StepIn, project: OwnedProject, session: DB):
    steps = steps_of(session, project.id)
    step = Step(project_id=project.id, title=body.title, instruction=body.instruction, source_ref=body.source_ref)
    index = len(steps) if body.position is None else max(0, min(len(steps), body.position))
    steps.insert(index, step)
    _renumber(steps)
    session.add_all(steps)
    bump(session, project)
    session.commit()
    session.refresh(step)
    return step.model_dump(mode="json")


@router.patch("/steps/{step_id}")
def patch_step(body: StepPatch, pair: OwnedStep, session: DB):
    step, project = pair
    changes = body.model_dump(exclude_unset=True)
    if "result" in changes and changes["result"] not in ("unknown", "success", "failed", "partial"):
        raise HTTPException(422, "Hasil tidak dikenal.")
    if any(getattr(step, k) != v for k, v in changes.items()):
        for key, value in changes.items():
            setattr(step, key, value)
        touch_step(step)
        project.sections_reviewed = False
        bump(session, project)
        session.add(step)
        session.commit()
        session.refresh(step)
    return step.model_dump(mode="json")


@router.post("/steps/{step_id}/review")
def review_step(body: ReviewBody, pair: OwnedStep, session: DB):
    step, project = pair
    if body.reviewed and body.revision is not None and body.revision != step.revision:
        raise HTTPException(409, "Langkah berubah sejak ditinjau. Muat ulang lalu periksa kembali.")
    if body.reviewed:
        for fact in step.facts:
            fact["reviewed"] = True
        step.facts = list(step.facts)
    step.reviewed = body.reviewed
    bump(session, project)
    session.add(step)
    session.commit()
    session.refresh(step)
    return step.model_dump(mode="json")


@router.put("/projects/{project_id}/steps/order")
def reorder_steps(body: OrderBody, project: OwnedProject, session: DB):
    steps = {s.id: s for s in steps_of(session, project.id)}
    if set(body.ids) != set(steps) or len(body.ids) != len(steps):
        raise HTTPException(409, "Daftar langkah tidak cocok dengan data server.")
    ordered = [steps[i] for i in body.ids]
    _renumber(ordered)
    session.add_all(ordered)
    bump(session, project)
    session.commit()
    return [s.model_dump(mode="json") for s in ordered]


@router.delete("/steps/{step_id}", status_code=204)
def delete_step(pair: OwnedStep, session: DB):
    step, project = pair
    for item in session.exec(select(Evidence).where(Evidence.step_id == step.id)):
        item.step_id = None
        session.add(item)
    session.delete(step)
    remaining = [s for s in steps_of(session, project.id) if s.id != step.id]
    _renumber(remaining)
    session.add_all(remaining)
    bump(session, project)
    session.commit()


# ---------------------------------------------------------------- evidence

def _read_image(upload: UploadFile, limit: int) -> tuple[bytes, str, int, int, datetime | None]:
    data = upload.file.read(limit + 1)
    if len(data) > limit:
        raise HTTPException(413, f"{upload.filename}: melebihi batas ukuran.")
    try:
        with Image.open(io.BytesIO(data)) as image:
            fmt = image.format
            if fmt not in ("PNG", "JPEG", "WEBP"):
                raise HTTPException(415, f"{upload.filename}: hanya PNG, JPEG, atau WebP.")
            image.verify()  # must run straight after open; metadata is read from a second handle below
        with Image.open(io.BytesIO(data)) as image:
            width, height = image.size
            captured = None
            try:
                exif = image.getexif()
                stamp = exif.get_ifd(0x8769).get(36867) or exif.get(306)
                if stamp:
                    captured = datetime.strptime(str(stamp), "%Y:%m:%d %H:%M:%S")
            except (ValueError, TypeError, KeyError, AttributeError):
                captured = None
    except (UnidentifiedImageError, OSError, SyntaxError) as error:
        raise HTTPException(415, f"{upload.filename}: bukan gambar yang valid.") from error
    return data, {"PNG": ".png", "JPEG": ".jpg", "WEBP": ".webp"}[fmt], width, height, captured


@router.get("/projects/{project_id}/evidence")
def list_evidence(project: OwnedProject, session: DB, storage: Store):
    out = []
    for item in evidence_of(session, project.id):
        row = item.model_dump(mode="json")
        row["url"] = evidence_url(storage, project.user_id, item)
        out.append(row)
    return out


@router.post("/projects/{project_id}/evidence", status_code=201)
def upload_evidence(project: OwnedProject, session: DB, storage: Store, settings: Config,
                    files: list[UploadFile] = File(...), step_id: str | None = Form(default=None),
                    allow_duplicate: bool = Form(default=False)):
    if step_id:
        step = session.get(Step, step_id)
        if not step or step.project_id != project.id:
            raise HTTPException(404, "Langkah tujuan tidak ditemukan.")
    existing = {e.hash for e in evidence_of(session, project.id)}
    position = len([e for e in evidence_of(session, project.id) if e.step_id == step_id])
    created, skipped = [], []
    limit = settings.max_upload_mb * 1024 * 1024
    for upload in files:
        data, suffix, width, height, captured = _read_image(upload, limit)
        file_hash = hashlib.sha256(data).hexdigest()
        if file_hash in existing and not allow_duplicate:
            skipped.append({"name": upload.filename, "reason": "duplicate"})
            continue
        existing.add(file_hash)
        item = Evidence(project_id=project.id, step_id=step_id, position=position, name=upload.filename or "gambar",
                        hash=file_hash, width=width, height=height, captured_at=captured, path="")
        item.path = storage.relative(project.user_id, project.id, "evidence", item.id + suffix)
        storage.save(item.path, io.BytesIO(data))
        position += 1
        session.add(item)
        created.append(item)
    if step_id and created:
        touch_step(step)
        session.add(step)
    bump(session, project)
    session.commit()
    rows = []
    for item in created:
        session.refresh(item)
        row = item.model_dump(mode="json")
        row["url"] = evidence_url(storage, project.user_id, item)
        rows.append(row)
    return {"created": rows, "skipped": skipped}


class EvidencePatch(BaseModel):
    step_id: str | None = None
    position: int | None = None
    caption: str | None = None
    facts: list[dict[str, Any]] | None = None
    match: dict[str, Any] | None = None


@router.patch("/evidence/{evidence_id}")
def patch_evidence(body: EvidencePatch, pair: OwnedEvidence, session: DB, storage: Store):
    item, project = pair
    changes = body.model_dump(exclude_unset=True)
    touched: set[str | None] = {item.step_id}
    if "step_id" in changes and changes["step_id"] != item.step_id:
        if changes["step_id"]:
            target = session.get(Step, changes["step_id"])
            if not target or target.project_id != project.id:
                raise HTTPException(404, "Langkah tujuan tidak ditemukan.")
        item.step_id = changes["step_id"]
        touched.add(item.step_id)
        siblings = [e for e in evidence_of(session, project.id) if e.step_id == item.step_id and e.id != item.id]
        index = changes.get("position")
        siblings.insert(len(siblings) if index is None else max(0, min(len(siblings), index)), item)
        _renumber(siblings)
        session.add_all(siblings)
    elif "position" in changes and changes["position"] is not None:
        siblings = [e for e in evidence_of(session, project.id) if e.step_id == item.step_id and e.id != item.id]
        siblings.insert(max(0, min(len(siblings), changes["position"])), item)
        _renumber(siblings)
        session.add_all(siblings)
    for key in ("caption", "facts", "match"):
        if key in changes:
            setattr(item, key, changes[key])
    for step_id in touched:
        if step_id:
            step = session.get(Step, step_id)
            if step:
                touch_step(step)
                session.add(step)
    bump(session, project)
    session.add(item)
    session.commit()
    session.refresh(item)
    row = item.model_dump(mode="json")
    row["url"] = evidence_url(storage, project.user_id, item)
    return row


@router.put("/steps/{step_id}/evidence/order")
def reorder_evidence(body: OrderBody, pair: OwnedStep, session: DB):
    step, project = pair
    items = {e.id: e for e in evidence_of(session, project.id) if e.step_id == step.id}
    if set(body.ids) != set(items) or len(body.ids) != len(items):
        raise HTTPException(409, "Daftar gambar tidak cocok dengan data server.")
    ordered = [items[i] for i in body.ids]
    _renumber(ordered)
    session.add_all(ordered)
    touch_step(step)
    session.add(step)
    bump(session, project)
    session.commit()
    return [e.model_dump(mode="json") for e in ordered]


@router.delete("/evidence/{evidence_id}", status_code=204)
def delete_evidence(pair: OwnedEvidence, session: DB, storage: Store):
    item, project = pair
    if item.step_id:
        step = session.get(Step, item.step_id)
        if step:
            touch_step(step)
            session.add(step)
    storage.delete(item.path)
    session.delete(item)
    bump(session, project)
    session.commit()
