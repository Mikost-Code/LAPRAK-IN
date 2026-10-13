"""Human-readable module review, retaining validated structured storage."""
import json

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (QCheckBox, QDialog, QFormLayout, QHBoxLayout, QHeaderView,
    QLabel, QMessageBox, QScrollArea, QTableWidget, QTableWidgetItem, QTabWidget,
    QTextEdit, QVBoxLayout, QWidget)

from .ai import ModuleAnalysis
from .dialogs import button, label
from .storage import uid


class ModuleReviewDialog(QDialog):
    def __init__(self, workspace):
        super().__init__(workspace)
        self.workspace = workspace
        self.project = workspace.project
        self.module = self.project.get("module")
        self.loading = True
        self.setWindowTitle("Periksa tugas dari modul")
        available = self.screen().availableGeometry()
        self.resize(min(900, available.width() - 32), min(700, available.height() - 32))
        layout = QVBoxLayout(self)
        layout.addWidget(label("Apa yang harus dikerjakan?", "heading"))
        hint = label("Periksa instruksi dan halaman sumber. Daftar ini adalah panduan tugas, bukan bukti bahwa praktikum sudah dikerjakan.", "muted")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        tabs = QTabWidget()
        layout.addWidget(tabs, 1)
        tasks = QWidget()
        task_layout = QVBoxLayout(tasks)
        self.instructions = QTableWidget(0, 3)
        self.instructions.setHorizontalHeaderLabels(["Instruksi tugas", "Halaman", "Sumber"])
        self.instructions.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.instructions.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.instructions.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.instructions.setWordWrap(True)
        task_layout.addWidget(self.instructions)
        controls = QHBoxLayout()
        controls.addWidget(button("Tambah tugas", self.add_instruction))
        controls.addWidget(button("Hapus tugas terpilih", self.remove_instruction))
        controls.addStretch()
        task_layout.addLayout(controls)
        tabs.addTab(tasks, "Daftar tugas")
        summary = QWidget()
        form = QFormLayout(summary)
        self.fields = {}
        for key, caption in (("objectives", "Tujuan (satu per baris)"), ("theory", "Dasar teori"), ("tools", "Alat & bahan (satu per baris)")):
            editor = QTextEdit()
            editor.setMinimumHeight(60)
            editor.setAcceptRichText(False)
            self.fields[key] = editor
            form.addRow(caption, editor)
        tabs.addTab(summary, "Ringkasan")
        self.source = QTextEdit()
        self.source.setAcceptRichText(False)
        original = "\n\n".join(f"[Halaman PDF {p['page']}]\n{p['text'] or '[Teks belum terbaca; transkripsikan isi halaman di sini]'}" for p in self.module["pages"])
        self.source.setPlainText(self.project.get("module_manual_text", "") or original)
        tabs.addTab(self.source, "Teks modul")
        self.page_checks = {}
        checks = QWidget()
        checks_layout = QVBoxLayout(checks)
        checks_layout.addWidget(label("Halaman berikut memerlukan pembacaan atau transkripsi. Tandai hanya setelah isinya diperiksa.", "muted"))
        self.checks_layout = checks_layout
        checks_scroll = QScrollArea()
        checks_scroll.setWidgetResizable(True)
        checks_scroll.setWidget(checks)
        tabs.addTab(checks_scroll, "Halaman")
        self.status = QLabel("Perubahan disimpan otomatis sebagai draf.")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.create_steps = QCheckBox("Buat langkah dokumentasi untuk tugas yang belum dihubungkan")
        steps = self.project.steps()
        self.create_steps.setChecked(len(steps) <= 1 and not any(s["narrative"].strip() or s["notes"].strip() or s["facts"] or self.project.evidence(s["id"]) for s in steps))
        layout.addWidget(self.create_steps)
        actions = QHBoxLayout()
        ai_button = button("Bantu baca dengan AI", self.analyze)
        ai_button.setEnabled(bool(workspace.settings.get("model")))
        ai_button.setToolTip("Hubungkan AI di Persiapan, atau tambahkan tugas secara manual.")
        actions.addWidget(ai_button)
        self.pending_button = button("Gunakan draf AI yang tersedia", self.apply_pending)
        self.pending_button.setVisible(bool(self.project.get("module_analysis_pending")))
        actions.addWidget(self.pending_button)
        actions.addStretch()
        actions.addWidget(button("Tutup", self.reject))
        actions.addWidget(button("Gunakan sebagai panduan", self.approve, True))
        layout.addLayout(actions)
        analysis = self.project.get("module_analysis", {}) or {"unknown_pages": [p["page"] for p in self.module["pages"] if p["needs_vision"]]}
        try:
            analysis = json.loads(self.project.get("module_structure_draft", "")) or analysis
        except (ValueError, TypeError):
            pass
        self.fill(analysis)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(700)
        self.timer.timeout.connect(self.save_draft)
        self.instructions.itemChanged.connect(self.changed)
        for field in [self.source, *self.fields.values()]:
            field.textChanged.connect(self.changed)
        self.loading = False

    def fill(self, analysis):
        self.loading = True
        self.instructions.setRowCount(0)
        for instruction in analysis.get("instructions", []):
            self.add_instruction(instruction=instruction)
        for key, field in self.fields.items():
            value = analysis.get(key, "" if key == "theory" else [])
            field.setPlainText(value if isinstance(value, str) else "\n".join(value))
        unknown = set(analysis.get("unknown_pages", []))
        existing = set(self.page_checks)
        for number in sorted(unknown | existing):
            if number not in self.page_checks:
                check = QCheckBox(f"Halaman PDF {number} sudah saya baca dan periksa")
                check.toggled.connect(self.changed)
                self.checks_layout.addWidget(check)
                self.page_checks[number] = check
            self.page_checks[number].setChecked(number not in unknown)
        self.loading = False

    def add_instruction(self, checked=False, instruction=None):
        instruction = instruction or {"description": "", "page": 1, "evidence": ""}
        row = self.instructions.rowCount()
        self.instructions.insertRow(row)
        for col, key in enumerate(("description", "page", "evidence")):
            self.instructions.setItem(row, col, QTableWidgetItem(str(instruction[key])))
        self.instructions.setRowHeight(row, 54)
        self.changed()

    def remove_instruction(self):
        row = self.instructions.currentRow()
        if row >= 0:
            self.instructions.removeRow(row)
            self.changed()

    def changed(self, *_):
        if not self.loading and hasattr(self, "timer"):
            self.timer.start()
            self.status.setText("Menyimpan draf…")

    def draft(self):
        result = {key: field.toPlainText() if key == "theory" else [s.strip() for s in field.toPlainText().splitlines() if s.strip()] for key, field in self.fields.items()}
        result["instructions"] = []
        for row in range(self.instructions.rowCount()):
            values = [self.instructions.item(row, col).text().strip() if self.instructions.item(row, col) else "" for col in range(3)]
            result["instructions"].append(dict(description=values[0], page=values[1], evidence=values[2]))
        result["unknown_pages"] = [number for number, check in self.page_checks.items() if not check.isChecked()]
        return result

    def save_draft(self):
        self.timer.stop()
        draft = json.dumps(self.draft(), ensure_ascii=False, indent=2)
        source = self.source.toPlainText()
        if draft != self.project.get("module_structure_draft", "") or source != self.project.get("module_manual_text", ""):
            self.project.set("module_structure_draft", draft)
            self.project.set("module_manual_text", source)
            self.project.set("module_reviewed", False)
            self.project.bump()
        self.status.setText("Draf tersimpan. Periksa sebelum menggunakannya sebagai panduan.")

    def apply_pending(self):
        if self.timer.isActive():
            response = QMessageBox.question(self, "Ganti draf yang sedang diedit?", "Draf AI akan mengganti daftar tugas dan ringkasan yang sedang kamu edit.")
            if response != QMessageBox.StandardButton.Yes:
                return
        self.fill(self.project.get("module_analysis_pending", {}))
        self.save_draft()

    def analyze(self):
        self.save_draft()
        self.workspace.analyze_module()
        self.accept()

    def approve(self):
        try:
            result = ModuleAnalysis.model_validate(self.draft()).model_dump()
            if not result["instructions"] or any(not i["description"].strip() for i in result["instructions"]):
                raise ValueError("Isi setidaknya satu tugas; judul tugas tidak boleh kosong.")
            if any(not 1 <= i["page"] <= len(self.module["pages"]) for i in result["instructions"]):
                raise ValueError("Isi nomor halaman tugas sesuai halaman file PDF.")
            if result["unknown_pages"]:
                raise ValueError("Periksa halaman yang belum terbaca pada tab Halaman belum terbaca.")
            previous = self.project.get("instructions", [])
            instructions = []
            for instruction in result["instructions"]:
                existing = next((i for i in previous if i["description"] == instruction["description"] and i["page"] == instruction["page"]), None)
                instructions.append(dict(instruction, id=existing["id"] if existing else uid()))
            self.save_draft()
            self.project.set("instructions", instructions)
            self.project.set("module_analysis", result)
            self.project.set("module_structure_draft", json.dumps(result, ensure_ascii=False, indent=2))
            self.project.set("module_reviewed", True)
            if self.create_steps.isChecked():
                self.create_documentation_steps(instructions)
            self.project.bump()
            if self.workspace.pages.currentIndex() == 1:
                self.workspace.show_setup(2)
            self.accept()
        except (ValueError, TypeError):
            self.status.setText("Belum dapat digunakan: isi tugas dan nomor halaman PDF yang valid, lalu periksa halaman belum terbaca pada tab Halaman.")

    def create_documentation_steps(self, instructions):
        steps = self.project.steps()
        reusable = steps[0] if len(steps) == 1 and not (steps[0]["narrative"].strip() or steps[0]["notes"].strip() or steps[0]["facts"] or self.project.evidence(steps[0]["id"]) or steps[0].get("instruction_ids")) else None
        for instruction in instructions:
            if any(instruction["id"] in s.get("instruction_ids", []) for s in self.project.steps()):
                continue
            if reusable:
                identifier = reusable["id"]
                reusable = None
            else:
                identifier = self.project.add_step(instruction["description"])
            self.project.save_step(identifier, {"title": instruction["description"], "instruction_ids": [instruction["id"]]})

    def reject(self):
        if self.timer.isActive():
            self.save_draft()
        super().reject()
