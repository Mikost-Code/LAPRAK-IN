from __future__ import annotations

import io
import shutil
from typing import Any

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

from ..deps import DB, Config, OwnedProject, Store
from ..latex.slots import detect_slot_map, extract_zip, find_main, guess_engine, tex_files, validate_slot_map
from ..models import Template
from ..service import bump, ensure_sections, project_dir, template_of
from ..storage import inside

router = APIRouter(tags=["templates"])


def public(template: Template, storage) -> dict:
    data = template.model_dump(mode="json")
    root = storage.path(template.root)
    data["files"] = tex_files(root) if root.is_dir() else []
    return data


@router.get("/projects/{project_id}/template")
def get_template(project: OwnedProject, session: DB, storage: Store):
    template = template_of(session, project)
    return public(template, storage) if template else None


@router.post("/projects/{project_id}/template", status_code=201)
def upload_template(project: OwnedProject, session: DB, storage: Store, settings: Config, file: UploadFile = File(...)):
    name = file.filename or "template"
    if not name.lower().endswith(".zip"):
        raise HTTPException(415, "Unggah template sebagai ZIP (LaTeX). Konversi DOCX menyusul di tahap berikutnya.")
    root = project_dir(storage, project)
    upload_path = root / "upload" / "template.zip"
    storage.save(upload_path.relative_to(storage.root).as_posix(), file.file, settings.max_upload_mb * 4 * 1024 * 1024)
    destination = root / "template"
    shutil.rmtree(destination, ignore_errors=True)
    destination.mkdir(parents=True)
    try:
        extract_zip(upload_path, destination)
    except (ValueError, OSError) as error:
        shutil.rmtree(destination, ignore_errors=True)
        raise HTTPException(422, f"ZIP tidak dapat dipakai: {error}") from error
    old = template_of(session, project)
    if old:
        session.delete(old)
    template = Template(project_id=project.id, kind="latex", name=name[:-4], root=destination.relative_to(storage.root).as_posix())
    slot_map = detect_slot_map(destination)
    if slot_map:
        template.slot_map, template.engine, template.main_path, template.status = slot_map, slot_map["engine"], slot_map["main"], "mapped"
        template.name = slot_map["name"]
        template.message = "Template dikenali; slot terisi otomatis."
    else:
        main = find_main(destination)
        if main:
            template.main_path, template.engine = main, guess_engine(destination, main)
            template.message = "Tentukan slot identitas, dokumentasi, dan bagian naratif."
        else:
            template.message = "Berkas utama (dengan \\documentclass) tidak ditemukan; pilih secara manual."
        template.slot_map = {"schema_version": 2, "name": template.name, "main": template.main_path, "engine": template.engine,
                             "identity": {"commands": {}, "inputs": [], "marker": "% LAPRAK_IDENTITY"}, "slots": {}}
    session.add(template)
    session.flush()
    project.template_id = template.id
    ensure_sections(session, project, template.slot_map)
    bump(session, project)
    session.commit()
    session.refresh(template)
    return public(template, storage)


class SlotBody(BaseModel):
    slot_map: dict[str, Any]


@router.put("/projects/{project_id}/template/slots")
def set_slots(body: SlotBody, project: OwnedProject, session: DB, storage: Store):
    template = template_of(session, project)
    if not template:
        raise HTTPException(404, "Template belum diunggah.")
    try:
        slot_map = validate_slot_map(storage.path(template.root), body.slot_map)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    template.slot_map, template.engine, template.main_path = slot_map, slot_map["engine"], slot_map["main"]
    template.status, template.message = "mapped", "Slot tersimpan; jalankan kompilasi uji."
    ensure_sections(session, project, slot_map)
    session.add(template)
    bump(session, project)
    session.commit()
    session.refresh(template)
    return public(template, storage)


@router.get("/projects/{project_id}/template/file")
def read_template_file(path: str, project: OwnedProject, session: DB, storage: Store):
    template = template_of(session, project)
    if not template:
        raise HTTPException(404, "Template belum diunggah.")
    try:
        target = inside(storage.path(template.root), path)
    except ValueError as error:
        raise HTTPException(400, str(error)) from error
    if not target.is_file() or target.suffix.lower() not in (".tex", ".cls", ".sty", ".bib", ".txt", ".md"):
        raise HTTPException(404, "Berkas teks tidak ditemukan.")
    return {"path": path, "content": target.read_text(encoding="utf-8", errors="replace")[:400000]}


@router.delete("/projects/{project_id}/template", status_code=204)
def delete_template(project: OwnedProject, session: DB, storage: Store):
    template = template_of(session, project)
    if template:
        shutil.rmtree(storage.path(template.root), ignore_errors=True)
        session.delete(template)
        project.template_id = None
        bump(session, project)
        session.commit()
