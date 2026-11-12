from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, HTTPException
from sqlmodel import Session, select

from ..config import get_settings
from ..db import get_engine
from ..deps import DB, Config, OwnedProject, Store, get_storage
from ..latex.build import check_environment, compile_workspace, detect_compiler
from ..latex.render import generate
from ..models import Build, Project
from ..service import blockers, project_dir, snapshot, template_of

router = APIRouter(tags=["builds"])


def run_build(build_id: str) -> None:
    """Executed off the request thread. Phase 6 moves this into an arq worker with the TeX Live image."""
    settings = get_settings()
    storage = get_storage()
    with Session(get_engine(), expire_on_commit=False) as session:
        build = session.get(Build, build_id)
        project = session.get(Project, build.project_id)
        template = template_of(session, project)
        build.status = "running"
        session.add(build)
        session.commit()
        try:
            root = project_dir(storage, project)
            template_root = storage.path(template.root)
            workspace, main = generate(template_root, template.slot_map, snapshot(session, project), storage.root, root / "build")
            compiler = detect_compiler(template.engine, settings.tex_compiler)
            pdf, log = compile_workspace(main, template.engine, compiler, settings.build_timeout)
            final = pdf.parent.parent / "report.pdf"
            shutil.copy2(pdf, final)
            build.pdf_path = final.relative_to(storage.root).as_posix()
            build.workspace = workspace.relative_to(storage.root).as_posix()
            build.log = log[-20000:]
            build.status = "done"
        except Exception as error:  # noqa: BLE001 - any failure is reported to the user, never swallowed
            build.status = "failed"
            build.error = str(error)[:12000]
        build.finished_at = datetime.now(timezone.utc)
        session.add(build)
        session.commit()
        _prune(session, project, storage)


def _prune(session: Session, project: Project, storage, keep: int = 3) -> None:
    rows = list(session.exec(select(Build).where(Build.project_id == project.id).order_by(Build.created_at.desc())))
    for old in rows[keep:]:
        if old.workspace:
            shutil.rmtree(storage.root / old.workspace, ignore_errors=True)
            old.workspace = ""
            old.pdf_path = ""
            session.add(old)
    session.commit()


@router.get("/projects/{project_id}/builds")
def list_builds(project: OwnedProject, session: DB, storage: Store):
    rows = session.exec(select(Build).where(Build.project_id == project.id).order_by(Build.created_at.desc()))
    return [_public(b, project, storage) for b in rows]


def _public(build: Build, project: Project, storage) -> dict:
    data = build.model_dump(mode="json", exclude={"workspace"})
    data["pdf_url"] = "/api/files/" + storage.sign(build.pdf_path, project.user_id) if build.pdf_path and build.status == "done" else ""
    data["stale"] = build.revision != project.revision
    return data


@router.post("/projects/{project_id}/builds", status_code=202)
def start_build(project: OwnedProject, session: DB, storage: Store, tasks: BackgroundTasks, final: bool = False):
    template = template_of(session, project)
    if not template or template.status not in ("mapped", "verified"):
        raise HTTPException(409, "Template belum siap dipakai.")
    if final and blockers(session, project):
        raise HTTPException(409, "Masih ada kekurangan; PDF final terkunci sampai semuanya terpenuhi.")
    running = session.exec(select(Build).where(Build.project_id == project.id, Build.status.in_(("queued", "running")))).first()
    if running:
        raise HTTPException(409, "Masih ada kompilasi yang berjalan.")
    build = Build(project_id=project.id, revision=project.revision, final=final)
    session.add(build)
    session.commit()
    session.refresh(build)
    tasks.add_task(run_build, build.id)
    return _public(build, project, storage)


@router.get("/projects/{project_id}/builds/{build_id}")
def get_build(build_id: str, project: OwnedProject, session: DB, storage: Store):
    build = session.get(Build, build_id)
    if not build or build.project_id != project.id:
        raise HTTPException(404, "Build tidak ditemukan.")
    return _public(build, project, storage)


_latex_cache: dict[str, dict] = {}


@router.get("/system/latex")
def latex_status(settings: Config, storage: Store, refresh: bool = False):
    """Probe compile is slow (seconds); the result is cached per compiler path for the process lifetime."""
    compiler = detect_compiler(settings.tex_engine, settings.tex_compiler)
    key = compiler + "|" + settings.tex_engine
    if refresh or key not in _latex_cache:
        try:
            info = check_environment(compiler, settings.tex_engine, storage.root / "_probe") if compiler else {}
            _latex_cache[key] = {"available": bool(compiler), **info, "latexmk": bool(shutil.which("latexmk"))}
        except RuntimeError as error:
            _latex_cache[key] = {"available": False, "compiler": compiler, "error": str(error)[:2000]}
    return _latex_cache[key]
