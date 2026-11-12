"""AI orchestration without server-side provider calls.

prepare -> prompt package (text + signed image URLs + schema) that the browser sends to the user's provider.
complete -> raw model output comes back, is validated against the schema, stored as a Draft, and applied
            only where it cannot overwrite the user's own text.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import select

from ..ai import prompts
from ..deps import DB, CurrentUser, OwnedProject, Store
from ..models import Draft, Evidence, Project, Section, SourceDocument, Step
from ..service import bump, evidence_of, evidence_url, sections_of, steps_of, touch_step

router = APIRouter(tags=["ai"])
RESULT_WORDS = {"id": {"unknown": "belum diketahui", "success": "berhasil", "failed": "gagal", "partial": "sebagian berhasil"},
                "en": {"unknown": "unknown", "success": "success", "failed": "failed", "partial": "partial"}}


class PrepareBody(BaseModel):
    operation: str
    step_id: str | None = None
    section_id: str | None = None
    document_id: str | None = None
    evidence_ids: list[str] | None = None
    text: str = ""
    page_from: int | None = None
    page_to: int | None = None


class CompleteBody(BaseModel):
    operation: str
    raw: str | dict[str, Any]
    target: dict[str, Any] = Field(default_factory=dict)
    cache_key: str = ""


def _step(session, project: Project, step_id: str | None) -> Step:
    step = session.get(Step, step_id) if step_id else None
    if not step or step.project_id != project.id:
        raise HTTPException(404, "Langkah tidak ditemukan.")
    return step


def _images(storage, project: Project, rows: list[Evidence]) -> list[dict[str, str]]:
    return [{"evidence_id": e.id, "url": evidence_url(storage, project.user_id, e), "hash": e.hash} for e in rows]


def _step_context(step: Step, words) -> dict:
    return {"step": step.title, "instruction": step.instruction, "notes": step.notes,
            "facts": [f for f in step.facts if f.get("reviewed")] or ""}


def _previous_summary(steps: list[Step], current: Step) -> str:
    out = []
    for s in steps:
        if s.position >= current.position:
            break
        text = (s.narrative or s.instruction or "").strip().replace("\n", " ")
        if text:
            out.append(f"{s.position + 1}. {s.title}: {text[:300]}")
    return "\n".join(out)


@router.post("/projects/{project_id}/ai/prepare")
def prepare(body: PrepareBody, project: OwnedProject, session: DB, storage: Store):
    op, lang = body.operation, project.language
    steps = steps_of(session, project.id)
    evidence = evidence_of(session, project.id)
    words = RESULT_WORDS[lang]
    if op == "analyze_evidence":
        step = _step(session, project, body.step_id)
        rows = [e for e in evidence if e.step_id == step.id]
        if body.evidence_ids:
            rows = [e for e in rows if e.id in body.evidence_ids]
        if not rows:
            raise HTTPException(422, "Langkah ini belum memiliki gambar.")
        context = _step_context(step, words)
        context["images"] = [f"{i + 1}. {e.name} (id {e.id})" for i, e in enumerate(rows)]
        package = prompts.build(op, lang, context, _images(storage, project, rows), {"step_id": step.id, "revision": step.revision})
    elif op == "describe_step":
        step = _step(session, project, body.step_id)
        context = _step_context(step, words)
        context["result"] = words.get(step.result, step.result)
        context["previous"] = _previous_summary(steps, step)
        rows = [e for e in evidence if e.step_id == step.id]
        package = prompts.build(op, lang, context, _images(storage, project, rows), {"step_id": step.id, "revision": step.revision})
    elif op == "match_evidence":
        rows = [e for e in evidence if (body.evidence_ids and e.id in body.evidence_ids) or (not body.evidence_ids and e.step_id is None)]
        if not rows:
            raise HTTPException(422, "Tidak ada gambar yang perlu dicocokkan.")
        context = {"existing_steps": [{"step_id": s.id, "title": s.title, "instruction": s.instruction[:400]} for s in steps],
                   "images": [f"{i + 1}. {e.name} (id {e.id})" + (f", waktu {e.captured_at.isoformat()}" if e.captured_at else "") for i, e in enumerate(rows)]}
        package = prompts.build(op, lang, context, _images(storage, project, rows), {"evidence_ids": [e.id for e in rows]})
    elif op == "draft_section":
        section = session.get(Section, body.section_id) if body.section_id else None
        if not section or section.project_id != project.id:
            raise HTTPException(404, "Bagian tidak ditemukan.")
        reviewed = [s for s in steps if s.reviewed and not s.not_applicable.strip()]
        if not reviewed:
            raise HTTPException(422, "Belum ada langkah yang diperiksa; bagian naratif dibuat dari langkah yang sudah diperiksa.")
        context = {"section": section.title, "steps": [{"id": s.id, "title": s.title, "result": words.get(s.result, s.result),
                                                          "narrative": s.narrative, "facts": [f["value"] for f in s.facts]} for s in reviewed]}
        if body.text:
            context["notes"] = body.text
        package = prompts.build(op, lang, context, None, {"section_id": section.id, "revision": section.revision})
    elif op == "outline_document":
        doc = session.get(SourceDocument, body.document_id) if body.document_id else None
        if not doc or doc.project_id != project.id:
            raise HTTPException(404, "Dokumen sumber tidak ditemukan.")
        start, end = body.page_from or 1, body.page_to or len(doc.pages)
        pages = [p for p in doc.pages if start <= p["number"] <= end]
        context = {"document": [{"page": p["number"], "text": p["text"][:6000]} for p in pages]}
        package = prompts.build(op, lang, context, None, {"document_id": doc.id, "page_from": start, "page_to": end})
    elif op == "scan_template":
        if not body.text:
            raise HTTPException(422, "Kirim isi template yang akan dipindai.")
        package = prompts.build(op, lang, {"template": body.text[:60000]}, None, {})
    elif op == "probe":
        package = prompts.build(op, lang, {"text": body.text or "laprak-probe"}, None, {})
    else:
        raise HTTPException(422, "Operasi AI tidak dikenal.")
    return package.model_dump()


@router.post("/projects/{project_id}/ai/complete")
def complete(body: CompleteBody, project: OwnedProject, session: DB):
    op = body.operation
    try:
        content = prompts.validate(op, body.raw)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    target = body.target
    applied = False
    kind, target_id, revision = "project", "", 0
    if op in ("analyze_evidence", "describe_step"):
        step = _step(session, project, target.get("step_id"))
        kind, target_id, revision = "step", step.id, step.revision
        stale = target.get("revision") is not None and target["revision"] != step.revision
        if op == "analyze_evidence" and not stale and not step.facts:
            step.facts = content["facts"]
            if step.result == "unknown":
                step.result = content["result"]
            applied = True
        if op == "describe_step" and not stale and not step.narrative.strip():
            step.narrative = content["narrative"]
            applied = True
        if applied:
            touch_step(step)
            session.add(step)
    elif op == "draft_section":
        section = session.get(Section, target.get("section_id"))
        if not section or section.project_id != project.id:
            raise HTTPException(404, "Bagian tidak ditemukan.")
        kind, target_id, revision = "section", section.id, section.revision
        if target.get("revision") == section.revision and not section.content.strip():
            section.content = content["content"]
            section.revision += 1
            section.reviewed = False
            session.add(section)
            applied = True
    elif op == "match_evidence":
        kind = "evidence"
        allowed = set(target.get("evidence_ids", []))
        step_ids = {s.id for s in steps_of(session, project.id)}
        content["assignments"] = [a for a in content["assignments"] if a["evidence_id"] in allowed and (a["step_id"] in step_ids or a["step_id"] is None)]
        for item in evidence_of(session, project.id):
            match = next((a for a in content["assignments"] if a["evidence_id"] == item.id), None)
            if match:
                item.match = match
                session.add(item)
    elif op == "outline_document":
        doc = session.get(SourceDocument, target.get("document_id"))
        if not doc or doc.project_id != project.id:
            raise HTTPException(404, "Dokumen sumber tidak ditemukan.")
        kind, target_id = "document", doc.id
        doc.outline = content
        doc.reviewed = False
        session.add(doc)
        applied = True
    draft = Draft(project_id=project.id, operation=op, target_kind=kind, target_id=target_id, target_revision=revision,
                  content=content, applied=applied)
    session.add(draft)
    bump(session, project)
    session.commit()
    session.refresh(draft)
    return {"draft": draft.model_dump(mode="json"), "applied": applied, "content": content}


@router.get("/projects/{project_id}/drafts")
def list_drafts(project: OwnedProject, session: DB, target_kind: str | None = None, target_id: str | None = None):
    statement = select(Draft).where(Draft.project_id == project.id)
    if target_kind:
        statement = statement.where(Draft.target_kind == target_kind)
    if target_id:
        statement = statement.where(Draft.target_id == target_id)
    rows = session.exec(statement.order_by(Draft.created_at.desc()))
    return [d.model_dump(mode="json") for d in rows]


class ApplyBody(BaseModel):
    field: str = "narrative"  # narrative | facts | content


@router.post("/drafts/{draft_id}/apply")
def apply_draft(draft_id: str, body: ApplyBody, user: CurrentUser, session: DB):
    draft = session.get(Draft, draft_id)
    project = session.get(Project, draft.project_id) if draft else None
    if not draft or not project or project.user_id != user.id:
        raise HTTPException(404, "Draf tidak ditemukan.")
    if draft.target_kind == "step":
        step = _step(session, project, draft.target_id)
        if body.field == "facts" and "facts" in draft.content:
            step.facts = draft.content["facts"]
        elif "narrative" in draft.content:
            step.narrative = draft.content["narrative"]
        else:
            raise HTTPException(422, "Draf tidak memiliki isi yang bisa diterapkan.")
        touch_step(step)
        session.add(step)
    elif draft.target_kind == "section":
        section = session.get(Section, draft.target_id)
        if not section:
            raise HTTPException(404, "Bagian tidak ditemukan.")
        section.content = draft.content.get("content", "")
        section.revision += 1
        section.reviewed = False
        session.add(section)
    else:
        raise HTTPException(422, "Jenis draf ini diterapkan lewat alur lain.")
    draft.applied = True
    project.sections_reviewed = False
    session.add(draft)
    bump(session, project)
    session.commit()
    return {"ok": True}
