"""Explicit local RPC boundary for the React desktop UI; secrets never enter state."""
import json
from pathlib import Path
from threading import Event

from PySide6.QtCore import QObject, QTimer, QUrl, Signal, Slot
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QFileDialog, QLabel

from .ai import Adapter, Analysis, ModuleAnalysis, credential_profile, validate_provider_endpoint
from .app import Workspace
from .dialogs import capability_key
from .report import copy_template, detect_compiler
from .storage import Project, inside, uid

SECTIONS = ("summary", "theory", "tools", "tasks", "references", "discussion", "conclusion")
PUBLIC_SETTINGS = ("provider", "model", "endpoint", "engine", "compiler", "template", "vision", "auto", "timeout", "structured", "image_size", "max_jobs", "pdf_mb", "pdf_pages")


class BackendWorkspace(Workspace):
    def error(self, text):
        if hasattr(self, "react_bridge"):
            self.react_bridge.notice.emit(str(text))
        else:
            self.statusBar().showMessage(str(text))

    def review_module(self):
        self.refresh()

    def job_done(self, job, result):
        super().job_done(job, result)
        if hasattr(self, "react_bridge") and self.project:
            current = next((j for j in self.project.jobs() if j["id"] == job["id"]), {})
            if current.get("status") == "succeeded":
                self.react_bridge.notice.emit("Draf AI tersedia di Riwayat draf; tulisanmu tetap dipertahankan." if job.get("step_id") and current.get("error") else "Draf AI selesai. Periksa sebelum digunakan.")

    def job_failed(self, job, error):
        super().job_failed(job, error)
        if hasattr(self, "react_bridge"):
            self.react_bridge.notice.emit(str(error))


class ReactBridge(QObject):
    response = Signal(str)
    changed = Signal(str)
    notice = Signal(str)
    browser = Signal(str)
    close_ready = Signal()

    def __init__(self, workspace, parent=None):
        super().__init__(parent)
        self.workspace = workspace
        workspace.react_bridge = self
        defaults = dict(provider="GPT (login Codex)", endpoint="codex://local", model="", engine="xelatex", compiler=detect_compiler(), template=str(Path.cwd() / "template"),
                        vision=False, auto=False, timeout=90, structured="Prompt JSON", image_size=1600, max_jobs=10, pdf_mb=50, pdf_pages=200)
        for key, value in defaults.items():
            if workspace.settings.get(key) is None:
                workspace.settings[key] = value
        self.last_state = ""
        self.last_stamp = None
        self.operation = ""
        self.setup_status = QLabel()
        self.setup_status.check_status = self.setup_status
        self.browser.connect(lambda url: QDesktopServices.openUrl(QUrl(url)))
        self.timer = QTimer(self)
        self.timer.setInterval(600)
        self.timer.timeout.connect(self.publish)
        self.timer.start()

    def state(self):
        w = self.workspace
        p = w.project
        result = {"settings": {k: w.settings.get(k) for k in PUBLIC_SETTINGS}, "compilerReady": w.compiler_ready,
                  "aiTested": w.settings.get("capabilities", {}).get(capability_key(w.settings), {}),
                  "recent": [{"path": s, "name": Path(s).name} for s in w.settings.get("recent", []) if (Path(s) / "session.sqlite").is_file()],
                  "active": w.active, "busy": list(w.tasks), "operation": self.operation,
                  "setupStatus": self.setup_status.text(), "watching": bool(w.observer), "project": None}
        if p:
            images = [dict(e, url=QUrl.fromLocalFile(str(inside(p.root, e["path"]))).toString()) for e in p.evidence()]
            build = p.get("last_build", {})
            revisions = {}
            for step in p.steps():
                revisions[step["id"]] = [{"created": r[0], "data": json.loads(r[1])} for r in p.db.execute("SELECT created,data FROM revisions WHERE step_id=? ORDER BY rowid DESC LIMIT 20", (step["id"],))]
            jobs = [{k: j[k] for k in ("id", "kind", "status", "error", "attempts", "step_id")} for j in p.jobs()]
            result["project"] = {"path": str(p.root), "identity": p.get("identity", {}), "revision": p.get("revision", 0),
                "steps": p.steps(), "images": images, "module": p.get("module", {}), "moduleReviewed": p.get("module_reviewed", False),
                "moduleDraft": p.get("module_analysis", {}), "modulePending": p.get("module_analysis_pending", {}),
                "moduleManual": p.get("module_manual_text", ""),
                "instructions": p.get("instructions", []), "folder": p.get("folder_watch", ""), "blockers": p.blockers(),
                "sections": {k: p.get(k, "") for k in SECTIONS}, "sectionsReviewed": p.get("sections_reviewed", False),
                "sectionDrafts": {k: p.get(k + "_pending", "") for k in ("discussion", "conclusion")},
                "build": build, "pdfUrl": QUrl.fromLocalFile(str(inside(p.root, build["pdf"]))).toString() if build else "",
                "revisions": revisions, "jobs": jobs}
            draft = p.get("module_structure_draft", "")
            if draft:
                try:
                    result["project"]["moduleDraft"] = json.loads(draft)
                except ValueError:
                    pass
        return result

    def publish(self):
        w = self.workspace
        p = w.project
        settings = json.dumps({k: w.settings.get(k) for k in (*PUBLIC_SETTINGS, "capabilities", "recent")}, sort_keys=True)
        stamp = (str(p.root) if p else None, p.db.total_changes if p else 0,
                 p.db.execute("PRAGMA data_version").fetchone()[0] if p else 0,
                 w.active, tuple(w.tasks), settings, w.compiler_ready, bool(w.observer), self.operation, self.setup_status.text())
        if stamp == self.last_stamp:
            return
        self.last_stamp = stamp
        value = json.dumps(self.state(), ensure_ascii=False)
        if value != self.last_state:
            self.last_state = value
            self.changed.emit(value)

    @Slot(str)
    def request(self, raw):
        identifier = None
        try:
            message = json.loads(raw)
            identifier = message["id"]
            value = self.dispatch(message["method"], message.get("params", {}))
            self.response.emit(json.dumps({"id": identifier, "result": value}, ensure_ascii=False))
        except Exception as error:
            # No provider response bodies or credential material in errors.
            text = str(error) if isinstance(error, (ValueError, RuntimeError)) else "Operasi belum berhasil. Periksa data dan coba kembali."
            self.response.emit(json.dumps({"id": identifier, "error": text}, ensure_ascii=False))
        self.publish()

    def reload(self, selected=None):
        w = self.workspace
        selected = selected or w.active
        w.active = None
        w.refresh()
        if w.steps_list.count():
            index = next((i for i, s in enumerate(w.project.steps()) if s["id"] == selected), 0)
            w.select_step(index)

    def dispatch(self, method, args):
        w = self.workspace
        p = w.project
        if method in ("checkPdf", "buildPdf", "imageTransform", "analyzeStep", "analyzeModule", "uploadModule", "importImages"):
            self.operation = ""
        if method == "state":
            return self.state()
        if method == "closeApp":
            self.close_ready.emit()
            return True
        if method == "importProject":
            w.import_project()
            return True
        if method == "createReport":
            if w.tasks:
                raise ValueError("Tunggu atau batalkan proses aktif sebelum membuat laporan.")
            identity = args["identity"]
            if not identity.get("title", "").strip():
                raise ValueError("Isi judul laporan terlebih dahulu.")
            folder = QFileDialog.getExistingDirectory(self.parent(), "Pilih lokasi penyimpanan laporan")
            if not folder:
                return None
            root = Path(folder) / ("Laprak-" + uid()[:8])
            report = Project.create(root, identity)
            template = Path(w.settings.get("template", str(Path.cwd() / "template")))
            if template.is_dir():
                try:
                    report.set("template_manifest", copy_template(template, root / "template"))
                except ValueError as error:
                    self.notice.emit(str(error))
            report.close()
            w.load_project(root)
            return str(root)
        if method == "openReport":
            if w.tasks:
                raise ValueError("Tunggu atau batalkan proses aktif sebelum membuka laporan lain.")
            folder = args.get("path") or QFileDialog.getExistingDirectory(self.parent(), "Buka folder laporan Laprak")
            if folder:
                if not (Path(folder) / "session.sqlite").is_file():
                    raise ValueError("Folder ini tidak berisi laporan Laprak.")
                w.load_project(Path(folder))
                return folder
            return None
        if method == "saveSettings":
            config = dict(w.settings, **{k: v for k, v in args.items() if k in PUBLIC_SETTINGS})
            config.setdefault("provider", "GPT (login Codex)")
            config.setdefault("endpoint", "codex://local")
            config.setdefault("engine", "xelatex")
            config.setdefault("compiler", detect_compiler(config["engine"]))
            validate_provider_endpoint(config)
            ranges = {"timeout": (10, 300), "image_size": (512, 4096), "max_jobs": (1, 100), "pdf_mb": (1, 200), "pdf_pages": (1, 1000)}
            for key, (minimum, maximum) in ranges.items():
                if not isinstance(config.get(key), (int, float)) or not minimum <= config[key] <= maximum:
                    raise ValueError(f"{key} harus antara {minimum} dan {maximum}.")
            if config.get("vision") and not config.get("capabilities", {}).get(capability_key(config), {}).get("vision"):
                config["vision"] = False
            if args.get("secret"):
                if not w.credentials.put(credential_profile(config), args["secret"]):
                    self.notice.emit("Kredensial hanya tersedia selama aplikasi dibuka karena Credential Manager tidak tersedia.")
            if any(config.get(k) != w.settings.get(k) for k in ("engine", "compiler", "template")):
                w.compiler_ready = False
            if capability_key(config) != capability_key(w.settings):
                config["vision"] = False
            w.settings.update(config)
            w.persist_settings()
            w.refresh()
            return True
        if method == "chooseTemplate":
            path = QFileDialog.getExistingDirectory(self.parent(), "Pilih folder template LaTeX")
            if path:
                self.dispatch("saveSettings", {"template": path})
            return path
        if method == "connectGpt":
            if w.tasks:
                raise ValueError("Tunggu proses aktif selesai atau batalkan terlebih dahulu.")
            from .codex import login
            self.operation = "Selesaikan login di browser, lalu kembali ke Laprak."
            def done(model):
                w.settings.update(provider="GPT (login Codex)", endpoint="codex://local", model=model, vision=False, structured="Prompt JSON")
                w.persist_settings()
                self.operation = "Login berhasil. GPT terhubung; periksa kemampuan AI sebelum memakai screenshot."
            w.task("Login GPT", lambda cancel: login(self.browser.emit, cancel), done, self.failed)
            return True
        if method == "testAi":
            if w.tasks:
                raise ValueError("Tunggu proses aktif selesai.")
            config = dict(w.settings, vision=True)
            adapter = Adapter(config, w.credentials.get(credential_profile(config)))
            self.operation = "Memeriksa koneksi dan kemampuan membaca gambar…"
            def test(cancel):
                adapter.run('Isi narrative="Koneksi berhasil", facts=[], unknown=[], result="belum diketahui".', cancel=cancel)
                from PIL import Image, ImageDraw, ImageFont
                import tempfile, secrets
                code = secrets.token_hex(3).upper()
                image = Image.new("RGB", (800, 200), "white")
                ImageDraw.Draw(image).text((30, 55), code, fill="black", font=ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 72))
                vision = False
                with tempfile.TemporaryDirectory() as folder:
                    target = Path(folder) / "test.png"
                    image.save(target)
                    try:
                        result = adapter.run("Baca kode pada gambar; isi narrative hanya dengan kode tersebut.", images=[target], cancel=cancel)
                        vision = result["narrative"].strip() == code
                    except RuntimeError:
                        if cancel.is_set():
                            raise
                return {"text": True, "vision": vision}
            def done(result):
                w.settings.setdefault("capabilities", {})[capability_key(config)] = result
                w.settings["vision"] = result["vision"]
                w.persist_settings()
                self.operation = "AI teruji · gambar terbaca" if result["vision"] else "Teks teruji · gambar belum terbaca; gunakan penjelasan manual."
            w.task("Memeriksa AI", test, done, self.failed)
            return True
        if method == "cancel":
            w.queue_paused = True
            if p:
                for job in p.jobs():
                    if job["status"] in ("queued", "running"):
                        p.job_status(job["id"], "cancelled")
            w.cancel_tasks()
            self.operation = "Pembatalan diminta."
            return True
        if not p:
            raise ValueError("Buat atau buka laporan terlebih dahulu.")
        if method == "saveIdentity":
            p.set("identity", args)
            p.bump()
        elif method == "selectStep":
            self.reload(args["id"])
        elif method == "addStep":
            if not args.get("title", "").strip():
                raise ValueError("Isi judul langkah.")
            self.reload(p.add_step(args["title"].strip()))
        elif method == "saveStep":
            w.flush()
            identifier = args["id"]
            old = p.step(identifier)
            if not old:
                raise ValueError("Langkah tidak ditemukan.")
            changes = {k: v for k, v in args.items() if k in ("title", "notes", "narrative", "facts", "result", "instruction_ids", "not_applicable", "unknown")}
            if any(old.get(k) != v for k, v in changes.items()):
                p.record_revision(identifier, {"origin": "user", "narrative": old["narrative"], "facts": old["facts"]})
                p.save_step(identifier, changes)
            self.reload(identifier)
        elif method == "approveStep":
            identifier = args["id"]
            step = p.step(identifier)
            if not step:
                raise ValueError("Langkah tidak ditemukan.")
            checks = args.get("checks", [False, False])
            if len(checks) != 2 or not all(isinstance(value, bool) for value in checks):
                raise ValueError("Selesaikan kedua pemeriksaan.")
            snapshot = args.get("snapshot")
            if snapshot and (snapshot.get("narrative") != step["narrative"] or snapshot.get("facts") != step["facts"] or snapshot.get("evidenceIds") != [e["id"] for e in p.evidence(identifier)]):
                raise ValueError("Isi atau bukti berubah. Periksa kembali sebelum menandai selesai.")
            if not step.get("not_applicable", "").strip() and (not p.evidence(identifier) or not step["narrative"].strip() or not all(checks) or any(not f.get("reviewed") for f in step["facts"])):
                raise ValueError("Tambahkan screenshot, isi penjelasan, dan periksa seluruh data serta kedua pemeriksaan.")
            p.save_step(identifier, {"checks": checks, "reviewed": True}, invalidate=False)
            self.reload(identifier)
        elif method == "importImages":
            paths, _ = QFileDialog.getOpenFileNames(self.parent(), "Tambahkan screenshot", "", "Gambar (*.png *.jpg *.jpeg)")
            for path in paths:
                w.import_one(Path(path), w.active, manual=True)
        elif method == "uploadModule":
            w.upload_module()
        elif method == "viewModule":
            w.view_module()
        elif method == "saveModule":
            if w.tasks or any(j["status"] == "queued" for j in p.jobs()):
                raise ValueError("Tunggu analisis selesai atau batalkan sebelum menggunakan panduan.")
            module = p.get("module")
            result = ModuleAnalysis.model_validate(args["data"]).model_dump()
            if not module or not result["instructions"] or result["unknown_pages"] or any(not i["description"].strip() or not 1 <= i["page"] <= len(module["pages"]) for i in result["instructions"]):
                raise ValueError("Isi tugas dan halaman yang valid, lalu periksa semua halaman yang belum terbaca.")
            previous = p.get("instructions", [])
            instructions = []
            for instruction in result["instructions"]:
                match = next((i for i in previous if i["description"] == instruction["description"] and i["page"] == instruction["page"]), None)
                instructions.append(dict(instruction, id=match["id"] if match else uid()))
            p.set("module_analysis", result)
            p.set("module_structure_draft", json.dumps(result, ensure_ascii=False))
            p.set("instructions", instructions)
            p.set("module_reviewed", True)
            if args.get("createSteps"):
                from .module_review import ModuleReviewDialog
                helper = ModuleReviewDialog(w)
                helper.create_documentation_steps(instructions)
                helper.deleteLater()
            p.bump()
            self.reload()
        elif method == "draftModule":
            previous = p.get("module_structure_draft", "")
            try:
                previous = json.loads(previous)
            except ValueError:
                previous = {}
            if previous != args["data"] or p.get("module_manual_text", "") != args.get("source", ""):
                p.set("module_structure_draft", json.dumps(args["data"], ensure_ascii=False))
                p.set("module_manual_text", args.get("source", ""))
                p.set("module_reviewed", False)
                p.bump()
        elif method == "chooseFolder":
            w.choose_folder()
        elif method == "checkPdf":
            config = dict(w.settings)
            config.setdefault("engine", "xelatex")
            config.setdefault("template", str(Path.cwd() / "template"))
            config.setdefault("compiler", detect_compiler(config["engine"]))
            w.check_setup(config, self.setup_status)
        elif method == "buildPdf":
            if not w.compiler_ready:
                raise ValueError("Periksa kesiapan PDF terlebih dahulu.")
            w.build()
        elif method == "openPdf":
            w.open_pdf()
        elif method == "exportPdf":
            w.export_final()
        elif method == "exportProject":
            w.export_project()
        elif method == "duplicateProject":
            w.duplicate_session()
        elif method == "analyzeStep":
            w.queue_paused = False
            w.analyze_step()
        elif method == "analyzeModule":
            w.queue_paused = False
            w.analyze_module()
        elif method == "saveSections":
            values = args["values"]
            if any(p.get(k, "") != values.get(k, "") for k in SECTIONS):
                for key in SECTIONS:
                    p.set(key, values.get(key, ""))
                p.set("sections_reviewed", False)
                p.bump()
            desired = bool(args.get("reviewed"))
            if desired != p.get("sections_reviewed", False):
                p.set("sections_reviewed", desired)
                p.bump()
        elif method == "generateSection":
            kind = args["kind"]
            if kind not in ("discussion", "conclusion"):
                raise ValueError("Bagian laporan tidak tersedia.")
            steps = [s for s in p.steps() if s["reviewed"]]
            if not steps:
                raise ValueError("Periksa langkah praktikum terlebih dahulu.")
            w.enqueue("generate_" + kind, None, "Tulis " + ("pembahasan" if kind == "discussion" else "kesimpulan") + " berdasarkan langkah diperiksa, tanpa menambah fakta:\n" + json.dumps(steps, ensure_ascii=False))
        elif method == "changeImage":
            p.change_evidence(args["id"], target=args.get("target"), remove=args.get("remove", False), offset=args.get("offset", 0))
            self.reload()
        elif method == "imageTool":
            w.selected_evidence = next((image for image in p.evidence() if image["id"] == args["id"]), None)
            if not w.selected_evidence:
                raise ValueError("Screenshot tidak ditemukan.")
            actions = {"crop": w.crop_evidence, "resize": w.resize_evidence, "restore": w.restore_evidence}
            if args["tool"] not in actions:
                raise ValueError("Tindakan gambar tidak tersedia.")
            actions[args["tool"]]()
        elif method == "imageTransform":
            from .images import derivative
            image = next((e for e in p.evidence() if e["id"] == args["id"]), None)
            if not image:
                raise ValueError("Screenshot tidak ditemukan.")
            rect = args.get("rect")
            maximum = args.get("maximum")
            if rect is not None and (len(rect) != 4 or any(not isinstance(v, int) for v in rect)):
                raise ValueError("Isi koordinat, lebar, dan tinggi dengan angka bulat.")
            if maximum is not None and (not isinstance(maximum, int) or not 200 <= maximum <= 8000):
                raise ValueError("Sisi maksimum harus antara 200 dan 8000 piksel.")
            def done(path):
                p.set_derivative(image["id"], path)
                self.reload()
            w.task("Membuat salinan screenshot", lambda cancel: derivative(p.root, image["path"], rect, maximum), done, self.failed)
        elif method == "reorderSteps":
            p.reorder_steps(args["ids"])
            self.reload()
        elif method == "applyRevision":
            revisions = [json.loads(r[0]) for r in p.db.execute("SELECT data FROM revisions WHERE step_id=? ORDER BY rowid DESC LIMIT 20", (args["id"],))]
            if not 0 <= args["index"] < len(revisions):
                raise ValueError("Revisi tidak ditemukan.")
            revision = revisions[args["index"]]
            self.dispatch("saveStep", dict(id=args["id"], **{k: revision[k] for k in ("narrative", "facts", "result", "unknown") if k in revision}))
        elif method == "retryJob":
            job = next((j for j in p.jobs() if j["id"] == args["id"]), None)
            if not job or job["status"] not in ("failed", "interrupted", "cancelled"):
                raise ValueError("Proses ini tidak dapat dicoba ulang.")
            job["data"]["retry_at"] = 0
            with p.db:
                p.db.execute("UPDATE jobs SET data=?,attempts=0 WHERE id=?", (json.dumps(job["data"]), job["id"]))
            p.job_status(job["id"], "queued")
            w.queue_paused = False
        else:
            raise ValueError("Tindakan tidak tersedia.")
        w.refresh()
        return True

    def failed(self, error):
        self.operation = str(error)
        self.notice.emit(str(error))
