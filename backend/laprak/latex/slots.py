"""Slot map: where identity, step documentation and narrative sections live inside a user's LaTeX template."""
from __future__ import annotations

import json
import re
import shutil
import zipfile
from pathlib import Path

from ..storage import inside

ENGINES = ("xelatex", "lualatex", "pdflatex")
SCHEMA_VERSION = 2

ITERA_SLOT_MAP = {
    "schema_version": SCHEMA_VERSION,
    "name": "ITERA Laporan Praktikum B5",
    "main": "main.tex",
    "engine": "xelatex",
    "identity": {
        "commands": {"namapeserta": "name", "nim": "nim", "kelas": "class", "judul": "title", "pertemuan": "meeting",
                     "bulantahun": "month_year", "asistenA": "assistant_a", "asistenB": "assistant_b", "daftaranggota": "members"},
        "inputs": ["data/identitas", "data/kelas", "data/asisten", "data/anggota-kelompok", "data/laporan"],
        "marker": "% LAPRAK_IDENTITY",
    },
    "slots": {
        "documentation": {"file": "isi/dokumentasi.tex", "heading": "Dokumentasi Praktikum"},
        "theory": {"file": "isi/dasar-teori.tex", "heading": "Dasar Teori"},
        "tools": {"file": "isi/alat-dan-bahan.tex", "heading": "Alat dan Bahan"},
        "tasks": {"file": "isi/tugas.tex", "heading": "Tugas"},
        "references": {"file": "isi/referensi.tex", "heading": "Referensi"},
        "summary": {"file": "isi/rangkuman.tex", "heading": "Rangkuman Praktikum"},
    },
    "required_assets": ["aset/gambar/logo-itera.png", "aset/gambar/logo-fti.png", "aset/gambar/logo-if.png"],
}

IDENTITY_LABELS = {
    "id": {"name": "Nama", "nim": "NIM", "class": "Kelas", "title": "Judul", "meeting": "Pertemuan", "month_year": "Bulan/Tahun",
           "assistant_a": "Asisten 1", "assistant_b": "Asisten 2", "members": "Anggota kelompok"},
    "en": {"name": "Name", "nim": "Student ID", "class": "Class", "title": "Title", "meeting": "Session", "month_year": "Month/Year",
           "assistant_a": "Assistant 1", "assistant_b": "Assistant 2", "members": "Group members"},
}

SECTION_TITLES = {
    "id": {"documentation": "Dokumentasi", "discussion": "Pembahasan", "conclusion": "Kesimpulan", "theory": "Dasar Teori",
           "tools": "Alat dan Bahan", "tasks": "Tugas", "references": "Referensi", "summary": "Rangkuman"},
    "en": {"documentation": "Documentation", "discussion": "Discussion", "conclusion": "Conclusion", "theory": "Theory",
           "tools": "Tools and Materials", "tasks": "Assignments", "references": "References", "summary": "Summary"},
}


def validate_slot_map(root: Path, slot_map: dict) -> dict:
    for key in ("main", "engine", "identity", "slots"):
        if key not in slot_map:
            raise ValueError(f"Peta slot belum memiliki '{key}'.")
    if slot_map["engine"] not in ENGINES:
        raise ValueError("Engine template tidak didukung.")
    if not inside(root, slot_map["main"]).is_file():
        raise ValueError("Berkas utama template tidak ditemukan.")
    identity = slot_map["identity"]
    for command in identity.get("commands", {}):
        if not re.fullmatch(r"[A-Za-z]+", command):
            raise ValueError(f"Nama command identitas '{command}' harus berupa huruf.")
    if not identity.get("inputs") and not identity.get("marker"):
        raise ValueError("Identitas memerlukan daftar \\input yang diganti atau penanda % LAPRAK_IDENTITY.")
    if "documentation" not in slot_map["slots"]:
        raise ValueError("Slot 'documentation' wajib ada.")
    for key, slot in slot_map["slots"].items():
        if not isinstance(slot, dict) or "file" not in slot:
            raise ValueError(f"Slot '{key}' harus memiliki 'file'.")
        inside(root, slot["file"])
    for asset in slot_map.get("required_assets", []):
        if not inside(root, asset).is_file():
            raise ValueError(f"Aset wajib hilang: {asset}")
    slot_map["schema_version"] = SCHEMA_VERSION
    return slot_map


def detect_slot_map(root: Path) -> dict | None:
    """Known templates get a ready map; anything else goes through the slot-mapping UI."""
    main = root / "main.tex"
    if not main.is_file():
        return None
    content = main.read_text(encoding="utf-8", errors="replace")
    if "\\input{data/identitas}" in content and "\\input{isi/dokumentasi}" in content and "ITERA" in content:
        return json.loads(json.dumps(ITERA_SLOT_MAP))
    return None


def tex_files(root: Path) -> list[str]:
    return sorted(p.relative_to(root).as_posix() for p in root.rglob("*.tex") if p.is_file())


def find_main(root: Path) -> str | None:
    candidates = [f for f in tex_files(root) if "\\documentclass" in (root / f).read_text(encoding="utf-8", errors="replace")]
    if "main.tex" in candidates:
        return "main.tex"
    return candidates[0] if len(candidates) == 1 else None


def guess_engine(root: Path, main: str) -> str:
    content = (root / main).read_text(encoding="utf-8", errors="replace")
    if "fontspec" in content or "polyglossia" in content:
        return "xelatex"
    if "luacode" in content:
        return "lualatex"
    return "pdflatex"


def extract_zip(archive: Path, destination: Path, limit: int = 200 * 1024 * 1024) -> None:
    with zipfile.ZipFile(archive) as zf:
        if sum(info.file_size for info in zf.infolist()) > limit:
            raise ValueError("Template melebihi batas 200 MB.")
        for info in zf.infolist():
            inside(destination, info.filename)
            if (info.external_attr >> 16) & 0o170000 == 0o120000:
                raise ValueError("Symlink dalam ZIP tidak diizinkan.")
        zf.extractall(destination)
    # Collapse a single top-level folder so paths match what the user sees in their editor.
    entries = [p for p in destination.iterdir() if p.name != "__MACOSX"]
    if len(entries) == 1 and entries[0].is_dir():
        inner = entries[0]
        for item in inner.iterdir():
            shutil.move(str(item), destination / item.name)
        inner.rmdir()
    for junk in ("__MACOSX", ".git", "build"):
        shutil.rmtree(destination / junk, ignore_errors=True)
