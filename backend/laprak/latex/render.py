"""Turn a project snapshot plus a slot map into a compilable workspace. The source template is never modified."""
from __future__ import annotations

import shutil
import uuid
from pathlib import Path

from ..storage import inside
from .slots import SECTION_TITLES, validate_slot_map
from .text import body, escape

DRAFT_NOTICE = {"id": r"\textbf{Draf: isi belum diperiksa.}\par", "en": r"\textbf{Draft: content not yet reviewed.}\par"}
NOTES_LABEL = {"id": "Catatan pengguna", "en": "User notes"}
NA_LABEL = {"id": "Tidak berlaku", "en": "Not applicable"}


def identity_tex(identity: dict, commands: dict[str, str]) -> str:
    lines = []
    for command, key in commands.items():
        value = str(identity.get(key, "") or "")
        rendered = r"\\".join(escape(line) for line in value.splitlines()) if "\n" in value else escape(value)
        lines.append(f"\\newcommand{{\\{command}}}{{{rendered}}}")
    return "\n".join(lines) + "\n"


def documentation_tex(snapshot: dict, generated: Path, evidence_source: Path, evidence_root: Path, heading: str | None) -> str:
    lang = snapshot.get("language", "id")
    out = [f"\\section{{{escape(heading)}}}"] if heading else []
    for index, step in enumerate(snapshot["steps"], 1):
        out.append(f"\\subsection{{{index}. {escape(step['title'])}}}")
        if not step.get("reviewed"):
            out.append(DRAFT_NOTICE[lang])
        if step.get("not_applicable"):
            out.append(f"\\textit{{{NA_LABEL[lang]}:}} " + body(step["not_applicable"], generated))
        out.append(body(step.get("narrative", ""), generated))
        if step.get("notes"):
            out.append(f"\\par\\textit{{{NOTES_LABEL[lang]}:}} " + body(step["notes"], generated))
        for item in [e for e in snapshot["evidence"] if e["step_id"] == step["id"]]:
            source = inside(evidence_source, item["path"])
            safe = item["id"] + source.suffix.lower()
            shutil.copy2(source, evidence_root / safe)
            caption = item.get("caption") or item["name"]
            out += [r"\begin{figure}[htbp]\centering",
                    f"\\includegraphics[width=\\linewidth,height=0.65\\textheight,keepaspectratio]{{../screenshots/{safe}}}",
                    f"\\caption{{{escape(caption)}}}", r"\end{figure}", r"\clearpage"]  # flush per figure: no float overflow
        out.append(r"\clearpage")
    return "\n".join(out)


def generate(template_root: Path, slot_map: dict, snapshot: dict, evidence_source: Path, build_root: Path) -> tuple[Path, Path]:
    """Returns (workspace, main.tex inside the workspace)."""
    slot_map = validate_slot_map(template_root, slot_map)
    lang = snapshot.get("language", "id")
    workspace = build_root / uuid.uuid4().hex
    work_template = workspace / "template"
    shutil.copytree(template_root, work_template, ignore=shutil.ignore_patterns("build", ".git", "*.aux", "*.log", "*.synctex.gz", "*.pdf"))
    generated = workspace / "generated"
    screenshots = workspace / "screenshots"
    generated.mkdir()
    screenshots.mkdir()

    identity = slot_map["identity"]
    (generated / "identity.tex").write_text(identity_tex(snapshot["identity"], identity.get("commands", {})), encoding="utf-8")
    main = inside(work_template, slot_map["main"])
    content = main.read_text(encoding="utf-8")
    if "\\usepackage{listings}" not in content:
        content = content.replace(r"\begin{document}", "\\usepackage{listings}\n\\begin{document}", 1)
    replaced = False
    for index, value in enumerate(identity.get("inputs", [])):
        needle = "\\input{" + value + "}"
        if needle in content:
            content = content.replace(needle, "\\input{../generated/identity}" if not replaced else "% identity generated")
            replaced = True
    if not replaced and identity.get("marker"):
        content = content.replace(identity["marker"], "\\input{../generated/identity}")
    main.write_text(content, encoding="utf-8")

    sections = {s["key"]: s for s in snapshot.get("sections", [])}
    for key, slot in slot_map["slots"].items():
        heading = slot.get("heading")
        if key == "documentation":
            tex = documentation_tex(snapshot, generated, evidence_source, screenshots, heading)
        else:
            section = sections.get(key, {})
            title = heading or section.get("title") or SECTION_TITLES[lang].get(key, key.title())
            tex = f"\\section{{{escape(title)}}}\n" + body(section.get("content", ""), generated)
            if section and not section.get("reviewed") and section.get("content"):
                tex += "\n" + DRAFT_NOTICE[lang]
        (generated / f"{key}.tex").write_text(tex + "\n", encoding="utf-8")
        target = inside(work_template, slot["file"])
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(f"\\input{{../generated/{key}}}\n", encoding="utf-8")
    return workspace, main
