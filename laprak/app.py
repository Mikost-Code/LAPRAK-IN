from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from datetime import date
from pathlib import Path

from PySide6.QtCore import QObject, QSize, Qt, QThreadPool, QTimer, QUrl, Signal
from PySide6.QtGui import QAction, QDesktopServices, QFont, QFontDatabase, QFontMetrics, QIcon, QPixmap
from PySide6.QtPdf import QPdfDocument
from PySide6.QtPdfWidgets import QPdfView
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QDialog, QFileDialog, QFrame, QHBoxLayout,
                              QHeaderView, QInputDialog, QLabel, QLineEdit, QListWidget, QListWidgetItem,
                              QMainWindow, QMenu, QMessageBox, QPushButton, QScrollArea, QSizePolicy, QSlider,
                              QSplitter, QStyle, QTabWidget, QTableWidget, QTableWidgetItem, QTextEdit,
                              QVBoxLayout, QWidget)
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from .ai import Adapter, AIError, Analysis, Credentials, ModuleAnalysis, PROMPT_VERSION, credential_profile
from .dialogs import IdentityDialog, SettingsDialog, TextDialog, button, label
from .pdf import extract_module, render_pages
from .report import build_report, check_environment, copy_template, detect_compiler, validate_template
from .storage import Project, digest, inside, uid
from .style import STYLE
from .workers import Worker
from .images import derivative, prepare_image


class WatchBridge(QObject):
    file = Signal(str)


class WatchHandler(FileSystemEventHandler):
    def __init__(self, bridge):
        super().__init__()
        self.bridge = bridge

    def on_created(self, event):
        if not event.is_directory:
            self.bridge.file.emit(event.src_path)

    def on_modified(self, event):
        if not event.is_directory:
            self.bridge.file.emit(event.src_path)

    def on_moved(self, event):
        if not event.is_directory:
            self.bridge.file.emit(event.dest_path)


def panel():
    frame = QFrame()
    frame.setObjectName("panel")
    return frame


def row(*widgets):
    layout = QHBoxLayout()
    layout.setSpacing(10)
    for widget in widgets:
        if widget is None:
            layout.addStretch()
        else:
            layout.addWidget(widget)
    return layout


class Workspace(QMainWindow):
    def __init__(self, data_root: Path):
        super().__init__()
        self.data_root = data_root.resolve()
        self.data_root.mkdir(parents=True, exist_ok=True)
        self.settings_file = self.data_root / "settings.json"
        self.settings = json.loads(self.settings_file.read_text(encoding="utf-8")) if self.settings_file.exists() else {}
        self.credentials = Credentials()
        self.project = None
        self.active = None
        self.selected_evidence = None
        self.loading = False
        self.tasks = {}
        self.running_job = None
        self.queue_paused = False
        self.observer = None
        self.pending = {}
        self.import_queue = []
        self.import_busy = False
        self.bridge = WatchBridge()
        self.bridge.file.connect(self.watch_event)
        self.compiler_ready = False
        self.closing = False
        self.setWindowTitle("Laprak")
        self.setWindowIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileIcon))
        self.resize(1480, 920)
        self.setMinimumSize(1040, 720)
        self.save_timer = QTimer(self)
        self.save_timer.setSingleShot(True)
        self.save_timer.setInterval(700)
        self.save_timer.timeout.connect(self.flush)
        self.watch_timer = QTimer(self)
        self.watch_timer.setInterval(500)
        self.watch_timer.timeout.connect(self.stabilize_files)
        self.watch_timer.start()
        self.queue_timer = QTimer(self)
        self.queue_timer.setInterval(500)
        self.queue_timer.timeout.connect(self.pump_queue)
        self.queue_timer.start()
        self.make_ui()
        self.refresh()
        last = self.settings.get("last_project")
        if last and (Path(last) / "session.sqlite").is_file():
            self.load_project(Path(last))

    def make_ui(self):
        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        header = QFrame()
        header.setObjectName("bar")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(18, 10, 18, 10)
        sessions = button("Sesi", self.dashboard)
        sessions.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DirIcon))
        header_layout.addWidget(sessions)
        self.session_title = label("Workspace praktikum", "section")
        header_layout.addWidget(self.session_title)
        header_layout.addStretch()
        self.saved_label = label("Lokal · tanpa akun", "muted")
        header_layout.addWidget(self.saved_label)
        self.build_button = button("Build PDF", self.build)
        self.build_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileIcon))
        header_layout.addWidget(self.build_button)
        self.export_button = button("Ekspor", self.export_menu, True)
        header_layout.addWidget(self.export_button)
        settings_button = button("Pengaturan", self.open_settings)
        header_layout.addWidget(settings_button)
        layout.addWidget(header)
        module_bar = QFrame()
        module_bar.setObjectName("bar")
        module_layout = QHBoxLayout(module_bar)
        module_layout.setContentsMargins(20, 8, 20, 8)
        self.module_label = label("Modul belum dipilih", "muted")
        module_layout.addWidget(self.module_label)
        self.upload_button = button("Upload modul", self.upload_module)
        self.upload_button.setObjectName("link")
        module_layout.addWidget(self.upload_button)
        self.view_module_button = button("Lihat modul", self.view_module)
        self.view_module_button.setObjectName("link")
        module_layout.addWidget(self.view_module_button)
        self.review_module_button = button("Periksa struktur", self.review_module)
        self.review_module_button.setObjectName("link")
        module_layout.addWidget(self.review_module_button)
        module_layout.addStretch()
        self.compiler_label = label("Compiler belum diperiksa", "muted")
        module_layout.addWidget(self.compiler_label)
        layout.addWidget(module_bar)
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setChildrenCollapsible(False)
        layout.addWidget(self.splitter, 1)
        left = panel()
        left.setMinimumWidth(250)
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(12, 12, 12, 12)
        self.add_button = button("+", self.add_step)
        self.add_button.setFixedSize(32, 32)
        self.add_button.setToolTip("Tambah langkah")
        left_layout.addLayout(row(label("Dokumentasi", "section"), None, self.add_button))
        self.steps_list = QListWidget()
        self.steps_list.setStyleSheet("QListWidget::item { padding: 0; border-radius: 5px; }")
        self.steps_list.currentRowChanged.connect(self.select_step)
        self.steps_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.steps_list.customContextMenuRequested.connect(self.step_context)
        left_layout.addWidget(self.steps_list, 3)
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        left_layout.addWidget(separator)
        left_layout.addWidget(label("Panduan modul", "section"))
        self.instructions = QListWidget()
        self.instructions.itemClicked.connect(self.map_instruction)
        left_layout.addWidget(self.instructions, 2)
        self.source_label = label("Unggah modul untuk melihat panduan.", "muted")
        self.source_label.setWordWrap(True)
        left_layout.addWidget(self.source_label)
        left_layout.addStretch()
        self.sections_button = button("Bagian laporan & checklist", self.report_sections)
        left_layout.addWidget(self.sections_button)
        self.folder_label = label("Folder screenshot belum dipilih", "muted")
        self.folder_label.setWordWrap(True)
        left_layout.addWidget(self.folder_label)
        self.folder_button = button("Pilih folder screenshot", self.choose_folder)
        left_layout.addWidget(self.folder_button)
        self.splitter.addWidget(left)
        center = panel()
        center.setMinimumWidth(390)
        center_layout = QVBoxLayout(center)
        center_layout.setContentsMargins(16, 14, 16, 12)
        self.step_title = label("Mulai dokumentasi", "heading")
        self.evidence_count = label("0 gambar", "muted")
        center_layout.addLayout(row(self.step_title, None, self.evidence_count))
        self.center_tabs = QTabWidget()
        center_layout.addWidget(self.center_tabs, 1)
        evidence_tab = QWidget()
        evidence_layout = QVBoxLayout(evidence_tab)
        evidence_layout.setContentsMargins(0, 14, 0, 0)
        self.image_area = QScrollArea()
        self.image_area.setWidgetResizable(True)
        self.image_area.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image = QLabel("Bukti praktikum akan tampil di sini.\n\nBuat sesi, unggah modul, lalu impor PNG atau JPEG.")
        self.image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image.setObjectName("muted")
        self.image.setMinimumSize(200, 220)
        self.image.setStyleSheet("background: #fafbfc; border: 1px solid #d9dfe3; border-radius: 5px;")
        self.image_area.setWidget(self.image)
        evidence_layout.addWidget(self.image_area, 1)
        self.thumbnails = QListWidget()
        self.thumbnails.setFlow(QListWidget.Flow.LeftToRight)
        self.thumbnails.setIconSize(QSize(92, 60))
        self.thumbnails.setViewMode(QListWidget.ViewMode.IconMode)
        self.thumbnails.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.thumbnails.setSpacing(5)
        self.thumbnails.setGridSize(QSize(120, 88))
        self.thumbnails.setWordWrap(False)
        self.thumbnails.setMaximumHeight(102)
        self.thumbnails.currentRowChanged.connect(self.show_evidence)
        self.thumbnails.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.thumbnails.customContextMenuRequested.connect(self.evidence_context)
        evidence_layout.addWidget(self.thumbnails)
        self.import_button = button("Impor gambar", self.import_images)
        self.analysis_button = button("Analisis", self.analyze_step)
        self.placement = QComboBox()
        self.placement.addItems(["Ke langkah aktif", "Buat langkah baru"])
        self.zoom = QSlider(Qt.Orientation.Horizontal)
        self.zoom.setRange(50, 200)
        self.zoom.setValue(100)
        self.zoom.setMaximumWidth(100)
        self.zoom.valueChanged.connect(self.render_image)
        evidence_layout.addLayout(row(self.import_button, self.analysis_button, None, label("Zoom", "muted"), self.zoom))
        evidence_layout.addLayout(row(label("Penempatan gambar", "muted"), self.placement))
        self.center_tabs.addTab(evidence_tab, "Bukti")
        facts_page = QWidget()
        facts_layout = QVBoxLayout(facts_page)
        facts_layout.addWidget(label("Koreksi nilai yang terbaca sebelum menyetujui langkah.", "muted"))
        self.facts_table = QTableWidget(0, 4)
        self.facts_table.setHorizontalHeaderLabels(["Tipe", "Nilai", "Sumber", "Diperiksa"])
        self.facts_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.facts_table.itemChanged.connect(self.dirty)
        facts_layout.addWidget(self.facts_table, 1)
        facts_layout.addLayout(row(button("Tambah fakta", self.add_fact), button("Hapus fakta", self.remove_fact), None))
        self.result_combo = QComboBox()
        self.result_combo.addItems(["belum diketahui", "sukses", "gagal", "sebagian sukses"])
        self.result_combo.currentTextChanged.connect(self.dirty)
        facts_layout.addLayout(row(label("Hasil pengujian"), self.result_combo))
        self.unknown_label = QLabel("")
        self.unknown_label.setWordWrap(True)
        facts_layout.addWidget(self.unknown_label)
        self.center_tabs.addTab(facts_page, "Fakta konfigurasi")
        self.step_context_label = label("Tahap aktif", "muted")
        center_layout.addLayout(row(label("Catatan langkah", "section"), None, self.step_context_label))
        self.notes = QLineEdit()
        self.notes.setPlaceholderText("Tindakan, tujuan, atau kendala yang tidak terlihat pada gambar")
        self.notes.textChanged.connect(self.dirty)
        center_layout.addWidget(self.notes)
        self.splitter.addWidget(center)
        right = panel()
        right.setMinimumWidth(330)
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(12, 0, 12, 14)
        self.right_tabs = QTabWidget()
        right_layout.addWidget(self.right_tabs, 1)
        narrative_page = QWidget()
        narrative_layout = QVBoxLayout(narrative_page)
        narrative_layout.setContentsMargins(0, 14, 0, 0)
        self.review_badge = label("Perlu diperiksa", "badge")
        narrative_layout.addLayout(row(label("Draf penjelasan", "section"), None, self.review_badge))
        self.narrative = QTextEdit()
        self.narrative.setAcceptRichText(False)
        self.narrative.setPlaceholderText("Tulis penjelasan secara manual atau analisis bukti dengan AI.\n\nJelaskan tindakan, tujuan konfigurasi, dan hasil yang benar-benar terlihat.")
        self.narrative.textChanged.connect(self.dirty)
        narrative_layout.addWidget(self.narrative, 1)
        warning = label("Periksa alamat IP dan hasil pengujian sebelum menyetujui.", "warning")
        warning.setWordWrap(True)
        narrative_layout.addWidget(warning)
        self.regenerate_button = button("Buat ulang", self.generate_narrative)
        self.approve_button = button("Setujui langkah", self.approve_step, True)
        narrative_layout.addLayout(row(self.regenerate_button, self.approve_button))
        narrative_layout.addWidget(label("Pemeriksaan", "section"))
        self.check_facts = QCheckBox("Fakta dan alamat tujuan sesuai bukti")
        self.check_result = QCheckBox("Hasil pengujian dan penjelasan sudah diperiksa")
        self.check_facts.toggled.connect(self.save_checks)
        self.check_result.toggled.connect(self.save_checks)
        narrative_layout.addWidget(self.check_facts)
        narrative_layout.addWidget(self.check_result)
        narrative_layout.addWidget(button("Riwayat revisi", self.revision_history))
        self.right_tabs.addTab(narrative_page, "Penjelasan")
        pdf_page = QWidget()
        pdf_layout = QVBoxLayout(pdf_page)
        self.pdf_status = label("Belum ada PDF. Periksa compiler, lalu Build PDF.", "muted")
        self.pdf_status.setWordWrap(True)
        pdf_layout.addWidget(self.pdf_status)
        self.pdf_document = QPdfDocument(self)
        self.pdf_view = QPdfView()
        self.pdf_view.setDocument(self.pdf_document)
        self.pdf_view.setPageMode(QPdfView.PageMode.MultiPage)
        self.pdf_view.setZoomMode(QPdfView.ZoomMode.FitToWidth)
        pdf_layout.addWidget(self.pdf_view, 1)
        pdf_layout.addWidget(button("Buka PDF di aplikasi lain", self.open_pdf))
        self.right_tabs.addTab(pdf_page, "Preview PDF")
        self.splitter.addWidget(right)
        self.splitter.setSizes([320, 650, 460])
        self.setCentralWidget(central)
        self.status_counts = label("0 langkah · 0 gambar", "muted")
        self.status_ai = label("AI belum dikonfigurasi", "muted")
        self.status_jobs = button("Antrean: 0", self.queue_dialog)
        self.status_jobs.setObjectName("link")
        self.cancel_button = button("Batalkan proses", self.cancel_tasks)
        self.cancel_button.setObjectName("link")
        self.cancel_button.setVisible(False)
        self.statusBar().addWidget(self.status_counts, 1)
        self.statusBar().addWidget(self.status_ai, 1)
        self.statusBar().addPermanentWidget(self.status_jobs)
        self.statusBar().addPermanentWidget(self.cancel_button)
        for key, function in (("Ctrl+N", self.new_session), ("Ctrl+O", self.open_session), ("Ctrl+S", self.flush), ("Ctrl+Return", self.approve_step)):
            action = QAction(self)
            action.setShortcut(key)
            action.triggered.connect(function)
            self.addAction(action)

    def error(self, text):
        QMessageBox.warning(self, "Perlu tindakan", str(text))

    def persist_settings(self):
        self.settings_file.write_text(json.dumps(self.settings, indent=2), encoding="utf-8")

    def task(self, name, function, done, failed=None):
        worker = Worker(function)
        task_id = uid()
        self.tasks[task_id] = worker
        self.cancel_button.setVisible(True)
        def finish(value, success):
            self.tasks.pop(task_id, None)
            self.cancel_button.setVisible(bool(self.tasks))
            if self.closing:
                return
            if success:
                if worker.cancel.is_set():
                    if failed:
                        failed(RuntimeError("Proses dibatalkan."))
                else:
                    done(value)
            elif failed:
                failed(value)
            else:
                self.error(value)
        worker.signals.done.connect(lambda value: finish(value, True))
        worker.signals.failed.connect(lambda error: finish(error, False))
        self.statusBar().showMessage(name)
        QThreadPool.globalInstance().start(worker)
        return worker

    def dashboard(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Sesi lokal")
        dialog.resize(620, 470)
        layout = QVBoxLayout(dialog)
        layout.addWidget(label("Laporan praktikum kamu", "heading"))
        layout.addWidget(label("Semua pekerjaan dan bukti tersimpan di perangkat ini.", "muted"))
        sessions = QListWidget()
        recent = [p for p in self.settings.get("recent", []) if (Path(p) / "session.sqlite").is_file()]
        for path in recent:
            sessions.addItem(Path(path).name + "\n" + path)
        if not recent:
            sessions.addItem("Belum ada sesi. Buat laporan praktikum pertamamu.")
        layout.addWidget(sessions, 1)
        def open_selected():
            index = sessions.currentRow()
            if 0 <= index < len(recent):
                dialog.accept()
                self.load_project(Path(recent[index]))
        sessions.itemDoubleClicked.connect(open_selected)
        layout.addLayout(row(button("Sesi baru", lambda: (dialog.accept(), self.new_session()), True),
                             button("Buka folder sesi", lambda: (dialog.accept(), self.open_session())),
                             button("Impor ZIP", lambda: (dialog.accept(), self.import_project()))))
        if self.project:
            layout.addWidget(button("Duplikasi sesi aktif", lambda: (dialog.accept(), self.duplicate_session())))
        dialog.exec()

    def new_session(self):
        if self.tasks:
            self.error("Selesaikan atau batalkan proses aktif sebelum mengganti sesi.")
            return
        dialog = IdentityDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        folder = QFileDialog.getExistingDirectory(self, "Pilih folder kosong untuk sesi")
        if not folder:
            return
        try:
            root = Path(folder)
            if any(root.iterdir()):
                raise ValueError("Gunakan folder kosong agar aset sesi terpisah dari file lain.")
            project = Project.create(root, dialog.values())
            template = Path(self.settings.get("template", Path.cwd() / "template"))
            if template.is_dir():
                try:
                    manifest = copy_template(template, root / "template")
                    project.set("template_manifest", manifest)
                except ValueError as error:
                    self.error(error)
            project.close()
            self.load_project(root)
            self.open_settings()
        except Exception as error:
            self.error(error)

    def open_session(self):
        folder = QFileDialog.getExistingDirectory(self, "Buka folder sesi Laprak")
        if folder:
            self.load_project(Path(folder))

    def load_project(self, root):
        if self.tasks:
            self.error("Selesaikan atau batalkan proses aktif sebelum mengganti sesi.")
            return
        if not (root / "session.sqlite").is_file():
            self.error("session.sqlite tidak ditemukan di folder tersebut.")
            return
        self.flush()
        try:
            project = Project(root)
        except Exception as error:
            self.error(error)
            return
        self.stop_watch()
        if self.project:
            self.project.close()
        self.project = project
        self.active = None
        self.compiler_ready = False
        self.queue_paused = False
        self.settings["last_project"] = str(root.resolve())
        recent = self.settings.get("recent", [])
        self.settings["recent"] = [str(root.resolve())] + [p for p in recent if p != str(root.resolve())][:15]
        self.persist_settings()
        self.refresh()
        if self.steps_list.count():
            self.select_step(0)
        folder = project.get("folder_watch", "")
        if folder and Path(folder).is_dir():
            self.start_watch(Path(folder))
        self.load_pdf()
        self.statusBar().showMessage("Sesi dipulihkan. Periksa compiler saat peluncuran ini sebelum build.", 8000)

    def refresh(self):
        self.loading = True
        self.steps_list.blockSignals(True)
        self.steps_list.clear()
        steps = self.project.steps() if self.project else []
        selected = 0
        for index, step in enumerate(steps):
            status = "✓ Diperiksa" if step["reviewed"] else "○ Perlu diperiksa"
            if step.get("not_applicable"):
                status = "Tidak berlaku"
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, step["id"])
            item.setSizeHint(QSize(270, 51))
            item.setToolTip(step["title"])
            self.steps_list.addItem(item)
            step_row = QWidget()
            step_layout = QHBoxLayout(step_row)
            step_layout.setContentsMargins(7, 5, 7, 5)
            step_layout.setSpacing(9)
            number = QLabel(f"{index+1:02}")
            number.setAlignment(Qt.AlignmentFlag.AlignCenter)
            number.setFixedSize(31, 31)
            number.setStyleSheet("font-weight: 600; " + ("background: #2d7136; color: white; border-radius: 15px;" if step["id"] == self.active else ""))
            title = QLabel(QFontMetrics(self.font()).elidedText(step["title"], Qt.TextElideMode.ElideRight, 118))
            title.setStyleSheet("font-weight: 600;" if step["id"] == self.active else "")
            state = label(status, "success" if step["reviewed"] else "muted")
            state.setStyleSheet("font-size: 11px;")
            step_layout.addWidget(number)
            step_layout.addWidget(title, 1)
            step_layout.addWidget(state)
            self.steps_list.setItemWidget(item, step_row)
            if step["id"] == self.active:
                selected = index
        if steps:
            self.steps_list.setCurrentRow(selected)
        self.steps_list.blockSignals(False)
        self.instructions.clear()
        if self.project:
            identity = self.project.get("identity", {})
            self.session_title.setText(f"Praktikum {identity.get('meeting', '01')}   /   {identity.get('title', '')}")
            module = self.project.get("module", {})
            self.module_label.setText(module.get("name", "Modul belum dipilih"))
            for instruction in self.project.get("instructions", []):
                mapped = any(instruction["id"] in s.get("instruction_ids", []) for s in steps)
                item = QListWidgetItem(("✓ " if mapped else "○ ") + instruction["description"])
                item.setToolTip(f"Halaman file {instruction['page']} · {instruction.get('evidence', '')}")
                item.setData(Qt.ItemDataRole.UserRole, instruction)
                self.instructions.addItem(item)
            self.source_label.setText("Struktur modul diperiksa" if self.project.get("module_reviewed") else "Struktur modul perlu diperiksa")
            self.status_counts.setText(f"{len(steps)} langkah · {len(self.project.evidence())} gambar")
            folder = self.project.get("folder_watch", "")
            self.folder_label.setText("Memantau · " + Path(folder).name if self.observer else "Folder screenshot belum dipilih")
            self.folder_label.setToolTip(folder)
            self.saved_label.setText("✓ Tersimpan")
            self.saved_label.setObjectName("success")
        enabled = bool(self.project)
        for widget in (self.add_button, self.upload_button, self.folder_button, self.export_button, self.sections_button):
            widget.setEnabled(enabled)
        for widget in (self.notes, self.narrative, self.import_button, self.analysis_button, self.regenerate_button,
                       self.approve_button, self.facts_table, self.result_combo, self.check_facts, self.check_result):
            widget.setEnabled(enabled and bool(self.active))
        self.build_button.setEnabled(enabled and self.compiler_ready)
        self.build_button.setToolTip("Periksa compiler dan template di Pengaturan terlebih dahulu." if not self.compiler_ready else "Bangun draf PDF dari revisi saat ini")
        self.compiler_label.setText((self.settings.get("engine", "xelatex") + " siap") if self.compiler_ready else "Compiler belum diperiksa")
        self.view_module_button.setEnabled(enabled and bool(self.project.get("module")))
        self.review_module_button.setEnabled(enabled and bool(self.project.get("module")))
        self.status_ai.setText("AI · " + self.settings["model"] if self.settings.get("model") else "AI belum dikonfigurasi · mode manual")
        pending = [j for j in self.project.jobs() if j["status"] in ("queued", "running", "interrupted", "failed")] if enabled else []
        self.status_jobs.setText(f"Antrean: {len(pending)}" + (" · jeda" if self.queue_paused else ""))
        self.loading = False

    def select_step(self, index):
        if self.loading or not self.project or index < 0:
            return
        self.flush()
        item = self.steps_list.item(index)
        if not item:
            return
        self.active = item.data(Qt.ItemDataRole.UserRole)
        step = self.project.step(self.active)
        self.loading = True
        self.step_title.setText(f"{index+1:02} · {step['title']}")
        mapped = [i for i in self.project.get("instructions", []) if i["id"] in step.get("instruction_ids", [])]
        self.step_context_label.setText("Halaman file " + ", ".join(str(i["page"]) for i in mapped) if mapped else "Tahap aktif")
        self.notes.setText(step["notes"])
        self.narrative.setPlainText(step["narrative"])
        self.result_combo.setCurrentText(step["result"])
        self.facts_table.setRowCount(0)
        for fact in step["facts"]:
            self.insert_fact(fact)
        self.check_facts.setChecked(step["checks"][0])
        self.check_result.setChecked(step["checks"][1])
        self.review_badge.setText("Diperiksa" if step["reviewed"] else "Perlu diperiksa")
        self.unknown_label.setText("Belum jelas: " + "; ".join(step.get("unknown", [])) if step.get("unknown") else "")
        self.loading = False
        self.refresh_evidence()
        self.refresh()

    def dirty(self, *_):
        if not self.loading and self.project and self.active:
            self.saved_label.setText("Menyimpan…")
            self.save_timer.start()

    def read_facts(self):
        result = []
        for index in range(self.facts_table.rowCount()):
            texts = [self.facts_table.item(index, col).text() if self.facts_table.item(index, col) else "" for col in range(3)]
            checked = self.facts_table.item(index, 3)
            result.append(dict(zip(("type", "value", "source"), texts), reviewed=checked.checkState() == Qt.CheckState.Checked))
        return result

    def flush(self):
        self.save_timer.stop()
        if self.loading or not self.project or not self.active:
            return
        step = self.project.step(self.active)
        if not step:
            return
        changes = dict(notes=self.notes.text(), narrative=self.narrative.toPlainText(), facts=self.read_facts(), result=self.result_combo.currentText())
        changed = any(step.get(k) != value for k, value in changes.items())
        if changed:
            self.project.record_revision(self.active, {"origin": "user", "narrative": step["narrative"], "facts": step["facts"]})
            self.project.save_step(self.active, changes)
            self.loading = True
            self.check_facts.setChecked(False)
            self.check_result.setChecked(False)
            self.loading = False
            self.review_badge.setText("Perlu diperiksa")
            self.refresh()
        self.saved_label.setText("✓ Tersimpan")
        self.pdf_staleness()

    def insert_fact(self, fact):
        index = self.facts_table.rowCount()
        self.facts_table.insertRow(index)
        for column, key in enumerate(("type", "value", "source")):
            self.facts_table.setItem(index, column, QTableWidgetItem(str(fact.get(key, ""))))
        checked = QTableWidgetItem()
        checked.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable)
        checked.setCheckState(Qt.CheckState.Checked if fact.get("reviewed") else Qt.CheckState.Unchecked)
        self.facts_table.setItem(index, 3, checked)

    def add_fact(self):
        self.loading = True
        self.insert_fact({"source": "catatan pengguna"})
        self.loading = False
        self.dirty()

    def remove_fact(self):
        index = self.facts_table.currentRow()
        if index >= 0:
            self.facts_table.removeRow(index)
            self.dirty()

    def save_checks(self):
        if self.loading or not self.project or not self.active:
            return
        facts, result = self.check_facts.isChecked(), self.check_result.isChecked()
        self.flush()
        self.project.save_step(self.active, {"checks": [facts, result]}, invalidate=False)
        self.loading = True
        self.check_facts.setChecked(facts)
        self.check_result.setChecked(result)
        self.loading = False

    def approve_step(self):
        if not self.project or not self.active:
            return
        self.flush()
        step = self.project.step(self.active)
        if not step.get("not_applicable"):
            if not self.project.evidence(self.active):
                self.error("Tambahkan bukti atau tandai langkah tidak berlaku dengan alasan.")
                return
            if not step["narrative"].strip() or not all(step["checks"]):
                self.error("Isi penjelasan dan selesaikan kedua pemeriksaan.")
                return
            if any(not fact.get("reviewed") for fact in step["facts"]):
                self.error("Periksa setiap fakta di tab Fakta konfigurasi.")
                return
        self.project.save_step(self.active, {"reviewed": True}, invalidate=False)
        self.review_badge.setText("Diperiksa")
        self.refresh()

    def add_step(self):
        if not self.project:
            return
        title, ok = QInputDialog.getText(self, "Langkah baru", "Judul langkah")
        if ok and title.strip():
            self.flush()
            step_id = self.project.add_step(title.strip())
            self.refresh()
            self.steps_list.setCurrentRow(len(self.project.steps())-1)
            if self.active != step_id:
                self.select_step(len(self.project.steps())-1)

    def step_context(self, position):
        if not self.active:
            return
        menu = QMenu(self)
        menu.addAction("Ubah judul", self.rename_step)
        menu.addAction("Naik", lambda: self.move_step(-1))
        menu.addAction("Turun", lambda: self.move_step(1))
        menu.addAction("Tidak berlaku / ubah alasan", self.not_applicable)
        menu.exec(self.steps_list.mapToGlobal(position))

    def rename_step(self):
        step = self.project.step(self.active)
        title, ok = QInputDialog.getText(self, "Judul langkah", "Judul", text=step["title"])
        if ok and title.strip():
            self.flush()
            self.project.save_step(self.active, {"title": title.strip()})
            self.refresh()
            self.select_step(self.steps_list.currentRow())

    def move_step(self, offset):
        self.flush()
        ids = [s["id"] for s in self.project.steps()]
        index = ids.index(self.active)
        other = max(0, min(len(ids)-1, index+offset))
        ids[index], ids[other] = ids[other], ids[index]
        self.project.reorder_steps(ids)
        self.refresh()
        self.select_step(other)

    def not_applicable(self):
        step = self.project.step(self.active)
        reason, ok = QInputDialog.getMultiLineText(self, "Tidak berlaku", "Alasan wajib. Kosongkan untuk mengembalikan langkah.", step.get("not_applicable", ""))
        if ok:
            self.project.save_step(self.active, {"not_applicable": reason.strip()})
            self.refresh()

    def refresh_evidence(self):
        self.thumbnails.blockSignals(True)
        self.thumbnails.clear()
        evidence = self.project.evidence(self.active) if self.project and self.active else []
        for item in evidence:
            path = inside(self.project.root, item["path"])
            widget = QListWidgetItem(QIcon(str(path)), QFontMetrics(self.font()).elidedText(item["name"], Qt.TextElideMode.ElideRight, 110))
            widget.setToolTip(item["name"])
            widget.setData(Qt.ItemDataRole.UserRole, item["id"])
            self.thumbnails.addItem(widget)
        self.thumbnails.blockSignals(False)
        self.evidence_count.setText(f"{len(evidence)} gambar")
        if evidence:
            self.thumbnails.setCurrentRow(0)
            self.show_evidence(0)
        else:
            self.selected_evidence = None
            self.image.clear()
            self.image.setText("Belum ada bukti untuk langkah ini.\n\nImpor gambar atau pilih folder screenshot.")

    def show_evidence(self, index):
        if not self.project or not self.active or index < 0:
            return
        items = self.project.evidence(self.active)
        if index < len(items):
            self.selected_evidence = items[index]
            self.render_image()

    def render_image(self):
        if not self.selected_evidence or not self.project:
            return
        path = inside(self.project.root, self.selected_evidence["path"])
        pixmap = QPixmap(str(path))
        if pixmap.isNull():
            self.image.setText("Gambar tidak dapat dibuka. Impor ulang sumber yang valid.")
            return
        area = self.image_area.viewport().size()
        target = QSize(max(200, area.width()-6), max(200, area.height()-6))
        target = target * (self.zoom.value()/100)
        scaled = pixmap.scaled(target, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        self.image.setPixmap(scaled)
        self.image.setMinimumSize(scaled.size())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        QTimer.singleShot(0, self.render_image)

    def import_images(self):
        if not self.project or not self.active:
            return
        paths, _ = QFileDialog.getOpenFileNames(self, "Impor screenshot", "", "Gambar (*.png *.jpg *.jpeg)")
        for path in paths:
            self.import_one(Path(path), self.active, manual=True)

    def import_one(self, path, step_id, manual=False):
        self.import_queue.append((path, step_id, manual, self.placement.currentIndex() == 1))
        self.pump_imports()

    def pump_imports(self):
        if self.import_busy or not self.import_queue or self.closing:
            return
        self.import_busy = True
        path, step_id, manual, new_step = self.import_queue.pop(0)
        self.flush()
        project = self.project
        def done(prepared):
            self.import_busy = False
            QTimer.singleShot(0, self.pump_imports)
            duplicate = project.db.execute("SELECT 1 FROM evidence WHERE hash=?", (prepared["hash"],)).fetchone()
            if duplicate and (not manual or QMessageBox.question(self, "Bukti duplikat", "Gambar identik sudah ada. Tetap tambahkan?") != QMessageBox.StandardButton.Yes):
                inside(project.root, prepared["path"]).unlink(missing_ok=True)
                return
            target_step = project.add_step(path.stem) if new_step else step_id
            project.register_image(prepared, target_step, bool(duplicate))
            self.refresh()
            if target_step == self.active:
                self.refresh_evidence()
                self.select_step(self.steps_list.currentRow())
            if self.settings.get("auto") and project.get("module_reviewed"):
                self.analyze_step(step_id=target_step)
        def failed(error):
            self.import_busy = False
            QTimer.singleShot(0, self.pump_imports)
            if manual:
                self.error(error)
            else:
                self.statusBar().showMessage(f"{path.name}: impor gagal. Periksa file lalu impor ulang. {error}", 10000)
        self.task("Mengimpor " + path.name, lambda cancel: prepare_image(project.root, path, cancel), done, failed)

    def evidence_context(self, position):
        if not self.selected_evidence:
            return
        menu = QMenu(self)
        menu.addAction("Geser ke kiri", lambda: self.change_evidence(offset=-1))
        menu.addAction("Geser ke kanan", lambda: self.change_evidence(offset=1))
        menu.addAction("Pindah ke langkah…", self.move_evidence)
        menu.addAction("Crop salinan…", self.crop_evidence)
        menu.addAction("Resize salinan…", self.resize_evidence)
        menu.addAction("Kembalikan gambar asli", self.restore_evidence)
        menu.addAction("Hapus dari laporan", lambda: self.change_evidence(remove=True))
        menu.exec(self.thumbnails.mapToGlobal(position))

    def derive_evidence(self, rect=None, maximum=None):
        evidence = dict(self.selected_evidence)
        original = self.project.get("evidence_original:" + evidence["id"], {"path": evidence["path"]})
        def done(path):
            self.project.set_derivative(evidence["id"], path)
            self.refresh_evidence()
            self.select_step(self.steps_list.currentRow())
        self.task("Membuat salinan gambar…", lambda cancel: derivative(self.project.root, original["path"], rect, maximum), done)

    def crop_evidence(self):
        value, ok = QInputDialog.getText(self, "Crop salinan", "Area pada gambar asli: x,y,lebar,tinggi (piksel)")
        if ok:
            try:
                rect = tuple(int(part.strip()) for part in value.split(","))
                if len(rect) != 4:
                    raise ValueError("Isi empat angka: x,y,lebar,tinggi.")
                self.derive_evidence(rect=rect)
            except ValueError as error:
                self.error(error)

    def resize_evidence(self):
        value, ok = QInputDialog.getInt(self, "Resize salinan", "Sisi maksimum (piksel), rasio tetap dijaga", 1600, 200, 8000)
        if ok:
            self.derive_evidence(maximum=value)

    def restore_evidence(self):
        evidence = self.selected_evidence
        original = self.project.get("evidence_original:" + evidence["id"])
        if original:
            self.project.set_derivative(evidence["id"], original["path"])
            self.refresh_evidence()
            self.select_step(self.steps_list.currentRow())

    def change_evidence(self, **kwargs):
        self.flush()
        self.project.change_evidence(self.selected_evidence["id"], **kwargs)
        self.refresh_evidence()
        self.refresh()
        self.select_step(self.steps_list.currentRow())

    def move_evidence(self):
        steps = self.project.steps()
        options = [f"{i+1:02} · {s['title']}" for i, s in enumerate(steps)]
        choice, ok = QInputDialog.getItem(self, "Pindah bukti", "Langkah tujuan", options, editable=False)
        if ok:
            self.change_evidence(target=steps[options.index(choice)]["id"])

    def choose_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Pilih folder screenshot eksternal")
        if folder:
            self.start_watch(Path(folder))

    def stop_watch(self):
        if self.observer:
            self.observer.stop()
            self.observer.join(timeout=2)
            self.observer = None
        self.pending.clear()

    def start_watch(self, folder):
        root = self.project.root
        folder = folder.resolve()
        if folder.is_relative_to(root) or root.is_relative_to(folder):
            self.error("Gunakan folder screenshot di luar folder sesi agar keluaran aplikasi tidak diimpor kembali.")
            return
        self.stop_watch()
        self.project.set("folder_watch", str(folder))
        self.observer = Observer()
        self.observer.schedule(WatchHandler(self.bridge), str(folder), recursive=False)
        self.observer.start()
        for path in folder.iterdir():
            if path.is_file():
                self.watch_event(str(path))
        self.refresh()

    def watch_event(self, path):
        if not self.project or not self.active or not self.observer:
            return
        source = Path(path)
        folder = Path(self.project.get("folder_watch", ""))
        if source.parent.resolve() != folder.resolve() or source.suffix.lower() not in (".png", ".jpg", ".jpeg") or source.name.startswith((".", "~")):
            return
        if str(source) not in self.pending:
            self.pending[str(source)] = {"step": self.active, "size": None, "stable": 0, "attempts": 0, "new_step": self.placement.currentIndex() == 1}

    def stabilize_files(self):
        for name, item in list(self.pending.items()):
            item["attempts"] += 1
            path = Path(name)
            try:
                stat = path.stat()
                size = (stat.st_size, stat.st_mtime_ns)
                item["stable"] = item["stable"]+1 if size == item["size"] and stat.st_size else 0
                item["size"] = size
                if item["stable"] >= 2:
                    previous = self.placement.currentIndex()
                    self.placement.setCurrentIndex(1 if item["new_step"] else 0)
                    try:
                        self.import_one(path, item["step"])
                    finally:
                        self.placement.setCurrentIndex(previous)
                    self.pending.pop(name, None)
            except Exception as error:
                if item["attempts"] >= 10:
                    self.statusBar().showMessage(f"Import gagal: {path.name}. Periksa file lalu impor manual. {error}", 10000)
                    self.pending.pop(name, None)

    def upload_module(self):
        source, _ = QFileDialog.getOpenFileName(self, "Pilih modul praktikum", "", "PDF (*.pdf)")
        if not source:
            return
        self.flush()
        project = self.project
        def extract(cancel):
            pages = extract_module(Path(source), self.settings.get("pdf_mb", 50), self.settings.get("pdf_pages", 200))
            if cancel.is_set():
                raise RuntimeError("Ekstraksi dibatalkan.")
            target = project.root / "module" / (uid() + ".pdf")
            shutil.copy2(source, target)
            render_pages(target, pages, target.parent / target.stem, cancel)
            for page in pages:
                page["image_path"] = page["image_path"].relative_to(project.root).as_posix()
            return {"name": Path(source).name, "path": target.relative_to(project.root).as_posix(), "hash": digest(target), "pages": pages}
        def done(module):
            project.set("module", module)
            project.set("module_reviewed", False)
            project.set("module_manual_text", "")
            project.set("module_analysis", {})
            project.set("module_analysis_pending", {})
            project.set("module_structure_draft", "")
            project.bump()
            for step in project.steps():
                project.save_step(step["id"], {"module_changed": module["hash"]})
            self.refresh()
            scans = [p["page"] for p in module["pages"] if p["needs_vision"]]
            self.source_label.setText(f"{len(module['pages'])} halaman · " + (f"halaman {scans} memerlukan vision/teks manual" if scans else "teks berhasil diekstrak, struktur belum diperiksa"))
            self.review_module()
        self.task("Membaca modul PDF…", extract, done)

    def view_module(self):
        if self.project and self.project.get("module"):
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(inside(self.project.root, self.project.get("module")["path"]))))

    def review_module(self):
        if not self.project or not self.project.get("module"):
            return
        self.flush()
        module = self.project.get("module")
        dialog = QDialog(self)
        dialog.setWindowTitle("Periksa struktur modul")
        dialog.resize(810, 680)
        layout = QVBoxLayout(dialog)
        layout.addWidget(label("Panduan praktikum", "heading"))
        layout.addWidget(label("Nomor halaman adalah halaman file PDF. Edit struktur sebelum menyetujuinya.", "muted"))
        tabs = QTabWidget()
        pages = QTextEdit()
        pages.setPlainText("\n\n".join(f"[Halaman file {p['page']}]\n{p['text'] or '[Teks belum terbaca: masukkan transkripsi manual]'}" for p in module["pages"]))
        tabs.addTab(pages, "Teks sumber (bisa dikoreksi)")
        structure = QTextEdit()
        default = {"objectives": [], "theory": "", "tools": [], "instructions": [],
                   "unknown_pages": [p["page"] for p in module["pages"] if p["needs_vision"]]}
        analysis = self.project.get("module_analysis", {}) or default
        structure.setPlainText(self.project.get("module_structure_draft", "") or json.dumps(analysis, ensure_ascii=False, indent=2))
        tabs.addTab(structure, "Struktur JSON")
        pending = self.project.get("module_analysis_pending", {})
        if pending:
            candidate_page = QWidget()
            candidate_layout = QVBoxLayout(candidate_page)
            candidate_text = QTextEdit()
            candidate_text.setReadOnly(True)
            candidate_text.setPlainText(json.dumps(pending, ensure_ascii=False, indent=2))
            candidate_layout.addWidget(candidate_text)
            candidate_layout.addWidget(button("Terapkan draf ke struktur untuk diperiksa", lambda: structure.setPlainText(candidate_text.toPlainText())))
            tabs.addTab(candidate_page, "Draf AI tersedia")
        layout.addWidget(tabs, 1)
        def save_text():
            # Corrected source is explicit user context; original page extraction remains stored.
            self.project.set("module_manual_text", pages.toPlainText())
            self.project.set("module_reviewed", False)
            self.project.bump()
        draft_timer = QTimer(dialog)
        draft_timer.setSingleShot(True)
        draft_timer.setInterval(700)
        def save_draft():
            self.project.set("module_manual_text", pages.toPlainText())
            self.project.set("module_structure_draft", structure.toPlainText())
            self.project.set("module_reviewed", False)
            self.project.bump()
        draft_timer.timeout.connect(save_draft)
        pages.textChanged.connect(lambda: draft_timer.start())
        structure.textChanged.connect(lambda: draft_timer.start())
        def analyze():
            save_text()
            self.analyze_module()
            dialog.accept()
        def approve():
            try:
                result = ModuleAnalysis.model_validate_json(structure.toPlainText()).model_dump()
                for instruction in result["instructions"]:
                    if not 1 <= instruction["page"] <= len(module["pages"]):
                        raise ValueError("Nomor halaman instruksi di luar PDF.")
                if result["unknown_pages"]:
                    raise ValueError("Selesaikan transkripsi/analisis halaman yang belum terbaca; hapus dari unknown_pages setelah diperiksa.")
                if not result["instructions"]:
                    raise ValueError("Tambahkan instruksi praktikum terlebih dahulu.")
                previous = self.project.get("instructions", [])
                instructions = []
                for instruction in result["instructions"]:
                    existing = next((p for p in previous if p["description"] == instruction["description"] and p["page"] == instruction["page"]), None)
                    instructions.append(dict(instruction, id=existing["id"] if existing else uid()))
                save_text()
                self.project.set("instructions", instructions)
                self.project.set("module_analysis", result)
                self.project.set("module_structure_draft", json.dumps(result, ensure_ascii=False, indent=2))
                self.project.set("module_reviewed", True)
                draft_timer.stop()
                self.refresh()
                dialog.accept()
            except Exception as error:
                self.error(error)
        layout.addLayout(row(button("Simpan teks", save_text), button("Analisis modul dengan AI", analyze), None,
                             button("Setujui struktur", approve, True)))
        dialog.exec()
        if draft_timer.isActive():
            draft_timer.stop()
            save_draft()

    def map_instruction(self, item):
        if not self.active:
            return
        self.flush()
        instruction = item.data(Qt.ItemDataRole.UserRole)
        step = self.project.step(self.active)
        ids = step.get("instruction_ids", [])
        if instruction["id"] in ids:
            ids.remove(instruction["id"])
        else:
            ids.append(instruction["id"])
        self.project.save_step(self.active, {"instruction_ids": ids})
        self.source_label.setText(f"Sumber: halaman file {instruction['page']}")
        self.refresh()

    def open_settings(self):
        dialog = SettingsDialog(self, dict(self.settings), self.credentials, self.check_setup)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            config = dialog.values()
            if any(config.get(k) != self.settings.get(k) for k in ("compiler", "engine", "template")):
                self.compiler_ready = False
            self.settings.update(config)
            self.persist_settings()
            self.queue_paused = False
            self.refresh()

    def check_setup(self, config, dialog):
        if self.tasks:
            dialog.check_status.setText("Tunggu proses aktif selesai sebelum memeriksa lingkungan.")
            return
        if not self.project:
            dialog.check_status.setText("Buat sesi terlebih dahulu. Template akan disalin dan diuji di folder sesi.")
            return
        try:
            if not (self.project.root / "template/main.tex").exists():
                manifest = copy_template(config["template"], self.project.root / "template")
                self.project.set("template_manifest", manifest)
            manifest = validate_template(self.project.root / "template")
            if config["engine"] != manifest["engine"]:
                raise ValueError(f"Manifest memerlukan {manifest['engine']}; sesuaikan pilihan engine.")
            compiler = detect_compiler(config["engine"], config["compiler"])
            dialog.check_status.setText("Memeriksa versi, dokumen kecil, dan template asli…")
            def done(result):
                self.compiler_ready = True
                self.settings.update(config, compiler=result["compiler"])
                self.persist_settings()
                dialog.check_status.setText("Siap · " + result["version"])
                self.refresh()
            self.task("Memeriksa compiler…", lambda cancel: check_environment(compiler, config["engine"], self.project.root / "template", self.project.root / "build/check", cancel),
                      done, lambda error: (setattr(self, "compiler_ready", False), dialog.check_status.setText(str(error)), self.refresh()))
        except Exception as error:
            dialog.check_status.setText(str(error))

    def provider(self, config=None):
        config = config or self.settings
        profile = credential_profile(config)
        return Adapter(config, self.credentials.get(profile))

    def enqueue(self, kind, step_id, prompt, images=(), extra=None):
        if not self.settings.get("model"):
            self.error("Pilih provider dan model di Pengaturan. Kamu tetap dapat menulis manual.")
            return
        jobs = self.project.jobs()
        if len([j for j in jobs if j["status"] in ("queued", "running")]) >= self.settings.get("max_jobs", 10):
            self.error("Batas antrean tercapai. Tunggu atau batalkan job yang belum diperlukan.")
            return
        adapter = self.provider()
        hashes = [digest(inside(self.project.root, path)) for path in images]
        key = adapter.cache_key(prompt, hashes)
        if any(j["data"].get("cache_key") == key and j["status"] in ("queued", "running") for j in jobs):
            self.statusBar().showMessage("Analisis input ini sudah ada di antrean.", 5000)
            return
        data = {"prompt": prompt, "images": list(images), "config": {k: self.settings[k] for k in ("provider", "endpoint", "model", "structured", "vision", "timeout", "image_size", "username") if k in self.settings},
                "cache_key": key, "prompt_version": PROMPT_VERSION}
        data.update(extra or {})
        self.project.add_job(kind, step_id, data)
        self.refresh()

    def analyze_step(self, *_args, step_id=None):
        if not self.project:
            return
        self.flush()
        if not self.project.get("module_reviewed"):
            self.error("Unggah modul dan setujui strukturnya sebelum analisis bukti.")
            return
        step_id = step_id or self.active
        step = self.project.step(step_id)
        evidence = self.project.evidence(step_id)
        if not evidence:
            self.error("Tambahkan screenshot terlebih dahulu.")
            return
        instructions = [i for i in self.project.get("instructions", []) if i["id"] in step.get("instruction_ids", [])]
        prompt = "Ekstrak fakta yang terlihat dan draf penjelasan. source memakai ID gambar atau 'catatan pengguna'.\n" + json.dumps(
            {"step": step["title"], "user_notes": step["notes"], "instructions": instructions,
             "evidence_ids_in_image_order": [e["id"] for e in evidence]}, ensure_ascii=False)
        self.enqueue("analyze_screenshot", step_id, prompt, [e["path"] for e in evidence])

    def generate_narrative(self):
        if not self.project or not self.active:
            return
        self.flush()
        step = self.project.step(self.active)
        if not step["facts"]:
            self.analyze_step()
            return
        if not all(f.get("reviewed") for f in step["facts"]):
            self.error("Periksa fakta sebelum membuat penjelasan dari fakta tersebut.")
            return
        self.enqueue("generate_explanation", self.active, "Buat penjelasan dari fakta diperiksa dan catatan user berikut. Jangan tambah fakta.\n" + json.dumps(step, ensure_ascii=False))

    def analyze_module(self):
        module = self.project.get("module")
        if not module:
            return
        if any(j["kind"] == "analyze_module" and j["status"] in ("queued", "running") for j in self.project.jobs()):
            self.error("Analisis modul ini masih berada di antrean. Tunggu atau batalkan terlebih dahulu.")
            return
        if not self.settings.get("model"):
            self.error("Pilih provider dan model di Pengaturan, atau isi struktur secara manual.")
            return
        manual = self.project.get("module_manual_text", "")
        scans = [p for p in module["pages"] if p["needs_vision"]]
        use_images = self.settings.get("vision", False)
        if scans and not use_images and (not manual or "[Teks belum terbaca" in manual):
            self.error("Modul scan memerlukan model vision yang telah diuji atau transkripsi teks manual.")
            return
        # Bound each request and retain page provenance; merge only after all chunks finish.
        batches = [module["pages"][i:i+5] for i in range(0, len(module["pages"]), 5)]
        outstanding = len([j for j in self.project.jobs() if j["status"] in ("queued", "running")])
        if outstanding + len(batches) > self.settings.get("max_jobs", 10):
            self.error(f"Modul memerlukan {len(batches)} permintaan. Naikkan batas antrean di Pengaturan atau periksa modul manual.")
            return
        group = uid()
        self.project.set("module_group:" + group, {"hash": module["hash"], "manual": manual, "results": {}, "total": len(batches)})
        for index, batch in enumerate(batches):
            text = "\n\n".join(f"Halaman file {p['page']}: {p['text']}" for p in batch)
            if manual:
                # Corrected text is bounded to matching page markers, not repeated whole-module input.
                import re
                pieces = re.split(r"\[Halaman file (\d+)\]", manual)
                if len(pieces) > 2:
                    texts = {int(pieces[i]): pieces[i+1] for i in range(1, len(pieces)-1, 2)}
                    text = "\n\n".join(f"Halaman file {p['page']}: {texts.get(p['page'], p['text'])}" for p in batch)
            if len(text) > 60000:
                self.error("Lima halaman melebihi batas konteks 60.000 karakter. Ringkas teks sumber manual.")
                return
            images = [p["image_path"] for p in batch if p.get("image_path")] if use_images else []
            self.enqueue("analyze_module", None, "Susun struktur bagian modul ini. Gabungkan teks/gambar tanpa menganggap instruksi telah dikerjakan. Pertahankan nomor halaman file " + str([p["page"] for p in batch]) + ".\n" + text,
                         images, {"module_group": group, "chunk": index})

    def pump_queue(self):
        if not self.project or self.running_job or self.queue_paused or any(self.tasks):
            return
        jobs = self.project.jobs()
        job = next((j for j in jobs if j["status"] == "queued" and j["data"].get("retry_at", 0) <= time.time()), None)
        if not job:
            return
        self.flush()
        self.running_job = job
        self.project.job_status(job["id"], "running", attempt=True)
        self.refresh()
        config = job["data"]["config"]
        try:
            adapter = self.provider(config)
        except Exception as error:
            self.job_failed(job, error)
            return
        images = [inside(self.project.root, path) for path in job["data"]["images"]]
        schema = ModuleAnalysis if job["kind"] == "analyze_module" else Analysis
        cached = self.project.get("cache:" + job["data"]["cache_key"])
        self.task("AI sedang bekerja · " + job["kind"], lambda cancel: cached if cached else adapter.run(job["data"]["prompt"], schema, images, cancel),
                  lambda result: self.job_done(job, result), lambda error: self.job_failed(job, error))

    def job_done(self, job, result):
        self.flush()
        self.running_job = None
        current = next(j for j in self.project.jobs() if j["id"] == job["id"])
        if current["status"] == "cancelled":
            self.refresh()
            return
        self.project.set("cache:" + job["data"]["cache_key"], result)
        if job["step_id"]:
            step = self.project.step(job["step_id"])
            self.project.record_revision(job["step_id"], dict(result, origin="AI", model=job["data"]["config"]["model"], input_revision=job["revision"]))
            if step["revision"] != job["revision"] or step["narrative"].strip():
                self.project.job_status(job["id"], "succeeded", "Revisi tersimpan; terapkan lewat Riwayat revisi agar edit tidak tertimpa.")
                self.statusBar().showMessage("Draf AI tersimpan di Riwayat revisi. Edit yang ada tetap dipertahankan.", 10000)
            else:
                changes = {k: result[k] for k in ("facts", "narrative", "unknown", "result") if k in result}
                self.project.save_step(job["step_id"], changes)
                self.project.job_status(job["id"], "succeeded")
        elif job["kind"] in ("generate_discussion", "generate_conclusion"):
            key = "discussion" if job["kind"] == "generate_discussion" else "conclusion"
            self.project.set(key + "_pending", result.get("narrative", ""))
            self.project.job_status(job["id"], "succeeded", "Draf tersedia pada Bagian laporan; periksa dan terapkan secara eksplisit.")
            self.statusBar().showMessage("Draf AI bagian laporan tersedia di Bagian laporan & checklist.", 10000)
        else:
            group_id = job["data"].get("module_group")
            group = self.project.get("module_group:" + group_id, {}) if group_id else {}
            if group:
                group["results"][str(job["data"]["chunk"])] = result
                self.project.set("module_group:" + group_id, group)
                self.project.job_status(job["id"], "succeeded")
                if len(group["results"]) != group["total"]:
                    self.refresh()
                    return
                merged = {"objectives": [], "theory": "", "tools": [], "instructions": [], "unknown_pages": []}
                for index in range(group["total"]):
                    part = group["results"][str(index)]
                    for key in ("objectives", "tools", "instructions", "unknown_pages"):
                        merged[key].extend(part.get(key, []))
                    merged["theory"] += part.get("theory", "") + "\n\n"
                result = merged
            if (group and (group["hash"] != self.project.get("module", {}).get("hash") or group["manual"] != self.project.get("module_manual_text", ""))) or self.project.get("module_reviewed"):
                self.project.set("module_analysis_pending", result)
                self.project.job_status(job["id"], "succeeded", "Respons berasal dari revisi lama; tersedia untuk pemeriksaan manual.")
            else:
                self.project.set("module_analysis_pending", result)
                self.project.job_status(job["id"], "succeeded")
                self.statusBar().showMessage("Analisis modul selesai. Buka Periksa struktur sebelum dipakai.", 10000)
        self.refresh()
        if self.active:
            self.select_step(self.steps_list.currentRow())

    def job_failed(self, job, error):
        self.running_job = None
        current = next(j for j in self.project.jobs() if j["id"] == job["id"])
        if current["status"] == "cancelled":
            self.refresh()
            return
        if isinstance(error, AIError) and error.auth:
            self.queue_paused = True
        if isinstance(error, AIError) and error.retryable and current["attempts"] < 3:
            data = current["data"]
            data["retry_at"] = time.time() + max(error.delay, 2**current["attempts"] * 2)
            with self.project.db:
                self.project.db.execute("UPDATE jobs SET data=? WHERE id=?", (json.dumps(data), job["id"]))
            self.project.job_status(job["id"], "queued", str(error))
        else:
            self.project.job_status(job["id"], "failed", str(error))
        self.statusBar().showMessage(str(error), 12000)
        self.refresh()

    def queue_dialog(self):
        if not self.project:
            return
        dialog = QDialog(self)
        dialog.setWindowTitle("Antrean AI")
        dialog.resize(720, 400)
        layout = QVBoxLayout(dialog)
        listing = QListWidget()
        jobs = self.project.jobs()
        for job in jobs:
            listing.addItem(f"{job['kind']} · {job['status']} · percobaan {job['attempts']}\n{job['error']}")
        layout.addWidget(listing)
        def retry():
            index = listing.currentRow()
            if index >= 0 and jobs[index]["status"] in ("failed", "interrupted", "cancelled"):
                data = jobs[index]["data"]
                data["retry_at"] = 0
                with self.project.db:
                    self.project.db.execute("UPDATE jobs SET data=?,attempts=0 WHERE id=?", (json.dumps(data), jobs[index]["id"]))
                self.project.job_status(jobs[index]["id"], "queued")
                self.queue_paused = False
                dialog.accept()
        def cancel():
            index = listing.currentRow()
            if index >= 0:
                self.project.job_status(jobs[index]["id"], "cancelled")
                if self.running_job and self.running_job["id"] == jobs[index]["id"]:
                    self.cancel_tasks()
                dialog.accept()
        layout.addLayout(row(button("Coba ulang", retry), button("Batalkan job", cancel), None,
                             button("Jeda / lanjut antrean", lambda: (setattr(self, "queue_paused", not self.queue_paused), dialog.accept()))))
        dialog.exec()
        self.refresh()

    def revision_history(self):
        if not self.project or not self.active:
            return
        self.flush()
        revisions = [(r[0], json.loads(r[1])) for r in self.project.db.execute("SELECT created,data FROM revisions WHERE step_id=? ORDER BY rowid DESC", (self.active,))]
        if not revisions:
            self.error("Belum ada revisi pada langkah ini.")
            return
        options = [f"{i+1}. {created[:19]} · {data.get('origin', 'user')}" for i, (created, data) in enumerate(revisions)]
        choice, ok = QInputDialog.getItem(self, "Riwayat revisi", "Pilih revisi untuk diperiksa", options, editable=False)
        if ok:
            data = revisions[options.index(choice)][1]
            dialog = TextDialog(self, "Periksa dan terapkan revisi", data.get("narrative", ""), "Simpan akan mengganti penjelasan saat ini secara eksplisit. Fakta diperiksa kembali.")
            if dialog.exec() == QDialog.DialogCode.Accepted:
                self.project.record_revision(self.active, {"origin": "user", "narrative": self.narrative.toPlainText(), "facts": self.read_facts()})
                self.project.save_step(self.active, {"narrative": dialog.editor.toPlainText(), "facts": data.get("facts", self.read_facts()),
                                                     "result": data.get("result", self.result_combo.currentText()), "unknown": data.get("unknown", [])})
                self.select_step(self.steps_list.currentRow())

    def report_sections(self):
        if not self.project:
            return
        self.flush()
        dialog = QDialog(self)
        dialog.setWindowTitle("Bagian laporan dan kelengkapan")
        dialog.resize(850, 700)
        layout = QVBoxLayout(dialog)
        tabs = QTabWidget()
        editors = {}
        for key, title in (("summary", "Rangkuman"), ("theory", "Teori"), ("tools", "Alat"), ("tasks", "Tugas"), ("references", "Referensi"), ("discussion", "Pembahasan"), ("conclusion", "Kesimpulan")):
            editor = QTextEdit()
            editor.setAcceptRichText(False)
            editor.setPlainText(self.project.get(key, ""))
            editor.setPlaceholderText(f"Isi {title.lower()} berdasarkan modul dan pekerjaan yang sudah diperiksa.")
            editors[key] = editor
            tabs.addTab(editor, title)
        for key in ("discussion", "conclusion"):
            pending = self.project.get(key + "_pending", "")
            if pending:
                candidate = QTextEdit()
                candidate.setReadOnly(True)
                candidate.setPlainText(pending)
                page = QWidget()
                candidate_layout = QVBoxLayout(page)
                candidate_layout.addWidget(candidate)
                candidate_layout.addWidget(button("Terapkan ke editor (tetap draf)", lambda _checked=False, k=key, p=pending: editors[k].setPlainText(p)))
                tabs.addTab(page, "Draf AI " + key)
        checklist = QTextEdit()
        checklist.setReadOnly(True)
        blockers = self.project.blockers()
        checklist.setPlainText("\n".join("○ " + item for item in blockers) if blockers else "✓ Semua pemeriksaan selesai. Hasil pengujian gagal tetap boleh diekspor jika telah didokumentasikan.")
        tabs.addTab(checklist, "Checklist")
        layout.addWidget(tabs)
        sections_review = QCheckBox("Saya sudah memeriksa semua bagian laporan dan sumbernya")
        sections_review.setChecked(self.project.get("sections_reviewed", False))
        layout.addWidget(sections_review)
        autosave = QTimer(dialog)
        autosave.setSingleShot(True)
        autosave.setInterval(700)
        def save_editors():
            changed = False
            for key, editor in editors.items():
                if self.project.get(key, "") != editor.toPlainText():
                    self.project.set(key, editor.toPlainText())
                    changed = True
            if changed:
                self.project.set("sections_reviewed", False)
                sections_review.blockSignals(True)
                sections_review.setChecked(False)
                sections_review.blockSignals(False)
                self.project.bump()
            self.pdf_staleness()
        autosave.timeout.connect(save_editors)
        for editor in editors.values():
            editor.textChanged.connect(lambda: autosave.start())
        def review_sections(checked):
            autosave.stop()
            save_editors()
            self.project.set("sections_reviewed", checked)
            sections_review.blockSignals(True)
            sections_review.setChecked(checked)
            sections_review.blockSignals(False)
            self.project.bump()
        sections_review.toggled.connect(review_sections)
        def save():
            autosave.stop()
            save_editors()
            dialog.accept()
        def generate(kind):
            steps = [s for s in self.project.steps() if s["reviewed"]]
            if not steps:
                self.error("Periksa dan setujui langkah sebelum membuat bagian laporan dengan AI.")
                return
            self.enqueue(kind, None, "Tulis " + ("pembahasan" if kind == "generate_discussion" else "kesimpulan") + " berdasarkan langkah diperiksa berikut. Tulis isi pada narrative; jangan tambah fakta atau keberhasilan.\n" + json.dumps(steps, ensure_ascii=False))
            dialog.accept()
        layout.addLayout(row(button("AI pembahasan", lambda: generate("generate_discussion")), button("AI kesimpulan", lambda: generate("generate_conclusion")), None,
                             button("Simpan bagian laporan", save, True)))
        layout.addWidget(button("Ubah identitas", self.edit_identity))
        dialog.exec()
        autosave.stop()
        save_editors()

    def edit_identity(self):
        dialog = IdentityDialog(self, self.project.get("identity", {}))
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.project.set("identity", dialog.values())
            self.project.bump()
            self.refresh()

    def build(self):
        if not self.project or not self.compiler_ready:
            return
        self.flush()
        if self.tasks:
            self.error("Tunggu proses aktif selesai sebelum memulai build.")
            return
        snapshot = self.project.snapshot()
        for key in ("summary", "theory", "tools", "tasks", "references"):
            snapshot[key] = self.project.get(key, "")
        self.build_button.setEnabled(False)
        self.pdf_status.setText("Membangun draf PDF… Preview terakhir dipertahankan.")
        def done(result):
            destination = self.project.root / "output/laporan.pdf"
            self.pdf_document.close()
            shutil.copy2(result["pdf"], destination)
            self.project.set("last_build", dict(result, pdf="output/laporan.pdf"))
            self.load_pdf()
            self.right_tabs.setCurrentIndex(1)
            self.refresh()
        def failed(error):
            self.pdf_status.setText("Build gagal. Preview terakhir dipertahankan.")
            self.refresh()
            self.error(error)
        self.task("Mengompilasi laporan…", lambda cancel: build_report(self.project.root, snapshot, self.settings["compiler"], cancel), done, failed)

    def load_pdf(self):
        self.pdf_document.close()
        build = self.project.get("last_build", {}) if self.project else {}
        if build and inside(self.project.root, build["pdf"]).is_file():
            self.pdf_document.load(str(inside(self.project.root, build["pdf"])))
        self.pdf_staleness()

    def pdf_staleness(self):
        if not self.project:
            return
        build = self.project.get("last_build", {})
        if not build:
            self.pdf_status.setText("Belum ada PDF. Periksa compiler, lalu Build PDF.")
        elif build["revision"] != self.project.get("revision", 0):
            self.pdf_status.setText("Preview revisi lama. Build ulang untuk memasukkan perubahan terbaru.")
        else:
            self.pdf_status.setText("Draf PDF · revisi " + str(build["revision"]) + (" · pemeriksaan belum lengkap" if self.project.blockers() else " · pemeriksaan lengkap"))

    def open_pdf(self):
        build = self.project.get("last_build", {}) if self.project else {}
        if build:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(inside(self.project.root, build["pdf"]))))

    def export_menu(self):
        if not self.project:
            return
        menu = QMenu(self)
        menu.addAction("Ekspor proyek ZIP (draf)", self.export_project)
        menu.addAction("Ekspor PDF final", self.export_final)
        menu.exec(self.export_button.mapToGlobal(self.export_button.rect().bottomLeft()))

    def export_project(self):
        self.flush()
        destination, _ = QFileDialog.getSaveFileName(self, "Ekspor proyek", self.project.root.name + ".zip", "ZIP (*.zip)")
        if destination:
            try:
                self.project.export_zip(Path(destination))
                self.statusBar().showMessage("Proyek diekspor tanpa kredensial.", 8000)
            except Exception as error:
                self.error(error)

    def export_final(self):
        self.flush()
        blockers = self.project.blockers()
        build = self.project.get("last_build", {})
        if not build or build["revision"] != self.project.get("revision", 0):
            blockers.append("Build PDF revisi terbaru terlebih dahulu.")
        if blockers:
            self.error("Ekspor final belum tersedia:\n\n" + "\n".join("• " + item for item in blockers))
            return
        destination, _ = QFileDialog.getSaveFileName(self, "Ekspor PDF final", "laporan.pdf", "PDF (*.pdf)")
        if destination:
            try:
                source = inside(self.project.root, build["pdf"])
                if Path(destination).resolve() != source.resolve():
                    shutil.copy2(source, destination)
                self.statusBar().showMessage("PDF final diekspor.", 8000)
            except Exception as error:
                self.error(error)

    def import_project(self):
        source, _ = QFileDialog.getOpenFileName(self, "Impor proyek", "", "ZIP (*.zip)")
        if not source:
            return
        destination = QFileDialog.getExistingDirectory(self, "Pilih folder kosong tujuan")
        if destination:
            try:
                result = Project.import_zip(Path(source), Path(destination))
                result.close()
                self.load_project(Path(destination))
            except Exception as error:
                self.error(error)

    def duplicate_session(self):
        if self.tasks:
            self.error("Selesaikan proses aktif terlebih dahulu.")
            return
        self.flush()
        destination = QFileDialog.getExistingDirectory(self, "Folder kosong untuk duplikasi")
        if destination:
            try:
                temporary = self.data_root / (uid() + ".zip")
                self.project.export_zip(temporary)
                clone = Project.import_zip(temporary, Path(destination))
                clone.close()
                temporary.unlink()
                self.load_project(Path(destination))
            except Exception as error:
                self.error(error)

    def cancel_tasks(self):
        for worker in self.tasks.values():
            worker.cancel.set()
        if self.running_job:
            self.project.job_status(self.running_job["id"], "cancelled")
        self.statusBar().showMessage("Pembatalan diminta. Respons AI tidak akan diterapkan; koneksi berakhir sesuai timeout.", 10000)

    def closeEvent(self, event):
        self.closing = True
        self.import_queue.clear()
        self.flush()
        self.stop_watch()
        self.cancel_tasks()
        if self.tasks:
            self.hide()
            self.queue_paused = True
            self.queue_timer.stop()
            self.watch_timer.stop()
            event.ignore()
            QTimer.singleShot(300, self.finish_close)
            return
        if self.project:
            self.project.close()
            self.project = None
        event.accept()

    def finish_close(self):
        if self.tasks:
            QTimer.singleShot(300, self.finish_close)
        else:
            self.close()


def configure_app(app):
    # Offscreen Qt on Windows does not always discover system font families.
    for name in ("segoeui.ttf", "segoeuib.ttf", "segoeuis.ttf", "seguisym.ttf"):
        font = Path("C:/Windows/Fonts") / name
        if font.is_file():
            QFontDatabase.addApplicationFont(str(font))
    app.setFont(QFont("Segoe UI", 10))
    app.setStyle("Fusion")
    # Keep native subcontrols consistent with our light stylesheet on dark Windows.
    app.setPalette(app.style().standardPalette())
    app.setStyleSheet(STYLE)


def main():
    parser = argparse.ArgumentParser(description="Laprak desktop workspace")
    parser.add_argument("--data-dir", type=Path, default=Path.cwd() / ".local")
    parser.add_argument("--session", type=Path)
    arguments = parser.parse_args()
    app = QApplication(sys.argv[:1])
    app.setApplicationName("Laprak")
    configure_app(app)
    window = Workspace(arguments.data_dir)
    if arguments.session:
        window.load_project(arguments.session)
    window.show()
    if not window.project:
        QTimer.singleShot(350, window.dashboard)
    sys.exit(app.exec())
