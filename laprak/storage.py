from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
import uuid
import zipfile
from datetime import datetime
from pathlib import Path

from PIL import Image


def uid() -> str:
    return uuid.uuid4().hex


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def inside(root: Path, relative: str) -> Path:
    target = (root / relative).resolve()
    if not target.is_relative_to(root.resolve()):
        raise ValueError("Path harus berada di dalam folder proyek.")
    return target


class Project:
    """One connection on the UI thread; workers receive immutable snapshots."""

    def __init__(self, root: Path):
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        for name in ("module", "screenshots/originals", "screenshots/derived", "template", "generated", "build", "output"):
            (self.root / name).mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.root / "session.sqlite")
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS steps(id TEXT PRIMARY KEY, position INTEGER, data TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS evidence(id TEXT PRIMARY KEY, step_id TEXT REFERENCES steps(id), position INTEGER, hash TEXT, path TEXT, name TEXT);
            CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY, kind TEXT, step_id TEXT, revision INTEGER, status TEXT, attempts INTEGER DEFAULT 0, data TEXT, error TEXT DEFAULT '');
            CREATE TABLE IF NOT EXISTS revisions(id TEXT PRIMARY KEY, step_id TEXT, created TEXT, data TEXT);
        """)
        version = self.get("schema_version", 1)
        if version != 1:
            self.db.close()
            raise ValueError(f"Schema proyek {version} belum didukung; proyek tidak diubah.")
        self.set("schema_version", 1)
        self.db.execute("UPDATE jobs SET status='interrupted', error='Aplikasi ditutup saat pekerjaan berjalan.' WHERE status='running'")
        self.db.commit()

    @classmethod
    def create(cls, root: Path, identity: dict):
        if (root / "session.sqlite").exists():
            raise ValueError("Folder ini sudah berisi sesi. Pilih folder kosong.")
        project = cls(root)
        project.set("identity", identity)
        project.set("revision", 0)
        project.set("module", {})
        project.set("instructions", [])
        project.set("module_reviewed", False)
        project.set("created", datetime.now().isoformat())
        project.add_step("Langkah pertama")
        return project

    def close(self):
        self.db.close()

    def get(self, key, default=None):
        row = self.db.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        return json.loads(row[0]) if row else default

    def set(self, key, value):
        with self.db:
            self.db.execute("INSERT OR REPLACE INTO meta VALUES(?,?)", (key, json.dumps(value, ensure_ascii=False)))

    def bump(self):
        revision = self.get("revision", 0) + 1
        self.set("revision", revision)
        return revision

    def steps(self):
        return [dict(json.loads(row[2]), id=row[0], position=row[1]) for row in self.db.execute("SELECT * FROM steps ORDER BY position")]

    def step(self, step_id):
        return next((s for s in self.steps() if s["id"] == step_id), None)

    def add_step(self, title):
        step_id = uid()
        data = dict(title=title, notes="", narrative="", facts=[], reviewed=False,
                    checks=[False, False], result="belum diketahui", instruction_ids=[], revision=0,
                    not_applicable="")
        with self.db:
            self.db.execute("INSERT INTO steps VALUES(?,?,?)", (step_id, len(self.steps()), json.dumps(data)))
            self.bump()
        return step_id

    def save_step(self, step_id, changes, invalidate=True):
        data = self.step(step_id)
        if not data:
            raise ValueError("Langkah tidak ditemukan.")
        if all(data.get(k) == v for k, v in changes.items()):
            return
        data.pop("id")
        data.pop("position")
        data.update(changes)
        data["revision"] += 1
        if invalidate:
            data["reviewed"] = False
            data["checks"] = [False, False]
        with self.db:
            self.db.execute("UPDATE steps SET data=? WHERE id=?", (json.dumps(data, ensure_ascii=False), step_id))
            self.bump()

    def reorder_steps(self, ids):
        if set(ids) != {s["id"] for s in self.steps()}:
            raise ValueError("Daftar langkah tidak cocok.")
        with self.db:
            for position, step_id in enumerate(ids):
                self.db.execute("UPDATE steps SET position=? WHERE id=?", (position, step_id))
            self.bump()

    def evidence(self, step_id=None):
        sql = "SELECT id,step_id,position,hash,path,name FROM evidence"
        args = ()
        if step_id:
            sql += " WHERE step_id=?"
            args = (step_id,)
        return [dict(zip(("id", "step_id", "position", "hash", "path", "name"), row))
                for row in self.db.execute(sql + " ORDER BY position", args)]

    def import_image(self, path: Path, step_id, allow_duplicate=False):
        if path.suffix.lower() not in (".png", ".jpg", ".jpeg"):
            raise ValueError("Format bukti harus PNG atau JPEG.")
        with Image.open(path) as im:
            if im.format not in ("PNG", "JPEG"):
                raise ValueError("Isi file bukan PNG/JPEG.")
            im.verify()
        file_hash = digest(path)
        if not allow_duplicate and self.db.execute("SELECT 1 FROM evidence WHERE hash=?", (file_hash,)).fetchone():
            raise FileExistsError("Gambar identik sudah ada di sesi.")
        evidence_id = uid()
        relative = f"screenshots/originals/{evidence_id}{path.suffix.lower()}"
        shutil.copy2(path, self.root / relative)
        with self.db:
            self.db.execute("INSERT INTO evidence VALUES(?,?,?,?,?,?)", (evidence_id, step_id, len(self.evidence(step_id)), file_hash, relative, path.name))
            self.save_step(step_id, {"evidence_changed": uid()})
        return evidence_id

    def change_evidence(self, evidence_id, target=None, remove=False, offset=0):
        evidence = next(e for e in self.evidence() if e["id"] == evidence_id)
        with self.db:
            if remove:
                self.db.execute("DELETE FROM evidence WHERE id=?", (evidence_id,))
            elif target:
                self.db.execute("UPDATE evidence SET step_id=?,position=? WHERE id=?", (target, len(self.evidence(target)), evidence_id))
                self.save_step(target, {"evidence_changed": uid()})
            else:
                items = self.evidence(evidence["step_id"])
                index = next(i for i, e in enumerate(items) if e["id"] == evidence_id)
                other = max(0, min(len(items)-1, index+offset))
                items[index], items[other] = items[other], items[index]
                for pos, item in enumerate(items):
                    self.db.execute("UPDATE evidence SET position=? WHERE id=?", (pos, item["id"]))
            self.save_step(evidence["step_id"], {"evidence_changed": uid()})

    def register_image(self, prepared, step_id, allow_duplicate=False):
        if not self.step(step_id):
            raise ValueError("Langkah tujuan sudah tidak tersedia.")
        if not allow_duplicate and self.db.execute("SELECT 1 FROM evidence WHERE hash=?", (prepared["hash"],)).fetchone():
            inside(self.root, prepared["path"]).unlink(missing_ok=True)
            raise FileExistsError("Gambar identik sudah ada.")
        with self.db:
            self.db.execute("INSERT INTO evidence VALUES(?,?,?,?,?,?)", (prepared["id"], step_id, len(self.evidence(step_id)), prepared["hash"], prepared["path"], prepared["name"]))
            self.db.execute("INSERT OR REPLACE INTO meta VALUES(?,?)", ("evidence_original:" + prepared["id"], json.dumps({"path": prepared["path"], "imported_at": datetime.now().isoformat(), "step_at_import": step_id})))
            self.save_step(step_id, {"evidence_changed": uid()})

    def set_derivative(self, evidence_id, path):
        evidence = next(e for e in self.evidence() if e["id"] == evidence_id)
        inside(self.root, path)
        original = self.get("evidence_original:" + evidence_id)
        if not original:
            self.set("evidence_original:" + evidence_id, {"path": evidence["path"]})
        with self.db:
            self.db.execute("UPDATE evidence SET path=? WHERE id=?", (path, evidence_id))
            self.save_step(evidence["step_id"], {"evidence_changed": uid()})

    def add_job(self, kind, step_id, data):
        job_id = uid()
        revision = self.step(step_id)["revision"] if step_id else self.get("revision", 0)
        with self.db:
            self.db.execute("INSERT INTO jobs(id,kind,step_id,revision,status,data) VALUES(?,?,?,?,?,?)",
                            (job_id, kind, step_id, revision, "queued", json.dumps(data, ensure_ascii=False)))
        return job_id

    def jobs(self):
        keys = ("id", "kind", "step_id", "revision", "status", "attempts", "data", "error")
        items = [dict(zip(keys, row)) for row in self.db.execute("SELECT * FROM jobs ORDER BY rowid")]
        for item in items:
            item["data"] = json.loads(item["data"])
        return items

    def job_status(self, job_id, status, error="", attempt=False):
        with self.db:
            self.db.execute("UPDATE jobs SET status=?,error=?,attempts=attempts+? WHERE id=?", (status, error, int(attempt), job_id))

    def record_revision(self, step_id, data):
        with self.db:
            self.db.execute("INSERT INTO revisions VALUES(?,?,?,?)", (uid(), step_id, datetime.now().isoformat(), json.dumps(data, ensure_ascii=False)))

    def snapshot(self):
        result = dict(schema_version=1, identity=self.get("identity", {}), module=self.get("module", {}),
                    module_reviewed=self.get("module_reviewed", False), instructions=self.get("instructions", []),
                    steps=self.steps(), evidence=self.evidence(), revision=self.get("revision", 0),
                    discussion=self.get("discussion", ""), conclusion=self.get("conclusion", ""))
        for key in ("summary", "theory", "tools", "tasks", "references"):
            result[key] = self.get(key, "")
        return result

    def blockers(self):
        result = []
        if not self.get("module"):
            result.append("Unggah modul PDF.")
        elif not self.get("module_reviewed"):
            result.append("Periksa dan setujui struktur modul.")
        for step in self.steps():
            if step.get("not_applicable", "").strip():
                continue
            if not self.evidence(step["id"]):
                result.append(f"{step['title']}: belum ada bukti.")
            if not step["reviewed"]:
                result.append(f"{step['title']}: perlu diperiksa.")
        for instruction in self.get("instructions", []):
            mapped = [s for s in self.steps() if instruction["id"] in s.get("instruction_ids", [])]
            if not mapped:
                result.append(f"Instruksi belum dipetakan: {instruction['description']}")
        if not self.get("discussion", "").strip() or not self.get("conclusion", "").strip():
            result.append("Isi pembahasan dan kesimpulan.")
        if not self.get("sections_reviewed", False):
            result.append("Periksa dan setujui bagian laporan beserta sumbernya.")
        return result

    def export_zip(self, destination: Path):
        if destination.resolve().is_relative_to(self.root):
            raise ValueError("Simpan ZIP di luar folder sesi.")
        self.db.commit()
        with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("manifest.json", json.dumps({"schema_version": 1, "format": "laprak-project"}))
            archive.writestr("portable.json", json.dumps(self.snapshot(), ensure_ascii=False, indent=2))
            # SQLite backup includes editor history and recoverable jobs, never credentials.
            backup_path = self.root / "output/export.sqlite"
            backup = sqlite3.connect(backup_path)
            try:
                self.db.backup(backup)
            finally:
                backup.close()
            archive.write(backup_path, "session.sqlite")
            for folder in ("module", "screenshots", "template", "generated", "output"):
                for path in (self.root / folder).rglob("*"):
                    if path.is_file() and not path.is_symlink() and path != backup_path and path.suffix.lower() not in (".log", ".sqlite"):
                        archive.write(path, path.relative_to(self.root).as_posix())
            build = self.get("last_build", {})
            workspace = Path(build.get("workspace", ""))
            if build and workspace.is_relative_to(self.root) and workspace.is_dir():
                for folder in ("template", "generated", "screenshots"):
                    for path in (workspace / folder).rglob("*"):
                        if path.is_file() and not path.is_symlink():
                            archive.write(path, "report/" + path.relative_to(workspace).as_posix())
            elif (self.root / "report").is_dir():
                for path in (self.root / "report").rglob("*"):
                    if path.is_file() and not path.is_symlink():
                        archive.write(path, path.relative_to(self.root).as_posix())
            backup_path.unlink(missing_ok=True)

    @classmethod
    def import_zip(cls, source: Path, destination: Path):
        if destination.exists() and any(destination.iterdir()):
            raise ValueError("Folder tujuan harus kosong.")
        with zipfile.ZipFile(source) as archive:
            if sum(f.file_size for f in archive.infolist()) > 1024**3:
                raise ValueError("Arsip melebihi batas 1 GB.")
            manifest = json.loads(archive.read("manifest.json"))
            if manifest != {"schema_version": 1, "format": "laprak-project"}:
                raise ValueError("Format arsip tidak didukung.")
            for info in archive.infolist():
                inside(destination, info.filename)
                if (info.external_attr >> 16) & 0o170000 == 0o120000:
                    raise ValueError("Symlink dalam ZIP tidak diizinkan.")
            if "session.sqlite" not in archive.namelist():
                raise ValueError("Data sesi tidak ditemukan.")
            archive.extractall(destination)
        result = cls(destination)
        for evidence in result.evidence():
            inside(destination, evidence["path"])
        result.set("folder_watch", "")
        result.set("compiler_verified", False)
        result.set("template_verified", False)
        build = result.get("last_build", {})
        if build:
            build.pop("workspace", None)
            result.set("last_build", build)
        return result
