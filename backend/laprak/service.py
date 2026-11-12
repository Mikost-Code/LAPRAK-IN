"""Shared project logic used by several routers: snapshots, revisions, blockers, signed evidence URLs."""
from __future__ import annotations

from pathlib import Path

from sqlmodel import Session, select

from .latex.slots import SECTION_TITLES
from .models import Evidence, Project, Section, Step, Template, now
from .storage import LocalStorage

MESSAGES = {
    "id": {
        "no_template": "Unggah template laporan.",
        "template_unmapped": "Lengkapi pemetaan slot template.",
        "no_steps": "Tambahkan minimal satu langkah dokumentasi.",
        "no_evidence": "{title}: belum ada gambar.",
        "not_reviewed": "{title}: perlu diperiksa.",
        "empty_section": "Isi bagian {title}.",
        "section_review": "Periksa dan setujui bagian naratif.",
        "unassigned": "{count} gambar belum ditempatkan ke langkah.",
    },
    "en": {
        "no_template": "Upload a report template.",
        "template_unmapped": "Finish the template slot mapping.",
        "no_steps": "Add at least one documentation step.",
        "no_evidence": "{title}: no images yet.",
        "not_reviewed": "{title}: needs review.",
        "empty_section": "Fill in the {title} section.",
        "section_review": "Review and approve the narrative sections.",
        "unassigned": "{count} images are not placed in a step.",
    },
}


def bump(session: Session, project: Project) -> int:
    project.revision += 1
    project.updated_at = now()
    session.add(project)
    return project.revision


def touch_step(step: Step, invalidate: bool = True) -> None:
    step.revision += 1
    step.updated_at = now()
    if invalidate:
        step.reviewed = False


def steps_of(session: Session, project_id: str) -> list[Step]:
    return list(session.exec(select(Step).where(Step.project_id == project_id).order_by(Step.position)))


def evidence_of(session: Session, project_id: str) -> list[Evidence]:
    return list(session.exec(select(Evidence).where(Evidence.project_id == project_id).order_by(Evidence.step_id, Evidence.position)))


def sections_of(session: Session, project_id: str) -> list[Section]:
    return list(session.exec(select(Section).where(Section.project_id == project_id).order_by(Section.position)))


def template_of(session: Session, project: Project) -> Template | None:
    return session.get(Template, project.template_id) if project.template_id else None


def ensure_sections(session: Session, project: Project, slot_map: dict) -> None:
    existing = {s.key for s in sections_of(session, project.id)}
    position = len(existing)
    for key, slot in slot_map.get("slots", {}).items():
        if key == "documentation" or key in existing:
            continue
        title = slot.get("heading") or SECTION_TITLES[project.language].get(key, key.title())
        session.add(Section(project_id=project.id, key=key, title=title, position=position))
        position += 1


def template_public(template: Template, storage: LocalStorage | None) -> dict:
    from .latex.slots import tex_files
    data = template.model_dump(mode="json")
    root = storage.path(template.root) if storage and template.root else None
    data["files"] = tex_files(root) if root and root.is_dir() else []
    return data


def project_dir(storage: LocalStorage, project: Project) -> Path:
    return storage.project_root(project.user_id, project.id)


def evidence_url(storage: LocalStorage, user_id: str, evidence: Evidence) -> str:
    return "/api/files/" + storage.sign(evidence.path, user_id)


def snapshot(session: Session, project: Project, storage: LocalStorage | None = None) -> dict:
    template = template_of(session, project)
    data = {
        "id": project.id, "title": project.title, "language": project.language, "identity": project.identity,
        "revision": project.revision, "ai_profile_id": project.ai_profile_id, "sections_reviewed": project.sections_reviewed,
        "updated_at": project.updated_at.isoformat(),
        "template": template_public(template, storage) if template else None,
        "steps": [s.model_dump(mode="json") for s in steps_of(session, project.id)],
        "evidence": [e.model_dump(mode="json") for e in evidence_of(session, project.id)],
        "sections": [s.model_dump(mode="json") for s in sections_of(session, project.id)],
    }
    if storage:
        for item, row in zip(data["evidence"], evidence_of(session, project.id)):
            item["url"] = evidence_url(storage, project.user_id, row)
    return data


def blockers(session: Session, project: Project) -> list[dict]:
    words = MESSAGES.get(project.language, MESSAGES["id"])
    out: list[dict] = []
    template = template_of(session, project)
    if not template:
        out.append({"message": words["no_template"], "target": "template"})
    elif template.status not in ("mapped", "verified"):
        out.append({"message": words["template_unmapped"], "target": "template"})
    steps = steps_of(session, project.id)
    evidence = evidence_of(session, project.id)
    if not steps:
        out.append({"message": words["no_steps"], "target": "steps"})
    by_step: dict[str | None, int] = {}
    for item in evidence:
        by_step[item.step_id] = by_step.get(item.step_id, 0) + 1
    if by_step.get(None):
        out.append({"message": words["unassigned"].format(count=by_step[None]), "target": "evidence"})
    for step in steps:
        if step.not_applicable.strip():
            continue
        if not by_step.get(step.id):
            out.append({"message": words["no_evidence"].format(title=step.title), "target": "step", "id": step.id})
        if not step.reviewed:
            out.append({"message": words["not_reviewed"].format(title=step.title), "target": "step", "id": step.id})
    for section in sections_of(session, project.id):
        if not section.content.strip():
            out.append({"message": words["empty_section"].format(title=section.title), "target": "section", "id": section.id})
    if not project.sections_reviewed:
        out.append({"message": words["section_review"], "target": "sections"})
    return out
