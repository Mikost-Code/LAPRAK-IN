"""Guided report workflow layered over the existing project operations."""
from pathlib import Path

from PySide6.QtCore import Qt, QSize
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QListWidget, QPushButton,
    QScrollArea, QSplitter, QStackedWidget, QVBoxLayout, QWidget)

from .dialogs import button, capability_key, label


def clear_layout(layout):
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget:
            widget.setParent(None)
            widget.deleteLater()
        elif item.layout():
            clear_layout(item.layout())


def page(title, description):
    widget = QWidget()
    widget.setObjectName("workflowPage")
    widget.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
    layout = QVBoxLayout(widget)
    layout.setContentsMargins(28, 24, 28, 24)
    layout.setSpacing(14)
    layout.addWidget(label(title, "heading"))
    subtitle = label(description, "muted")
    subtitle.setWordWrap(True)
    layout.addWidget(subtitle)
    return widget, layout


class Workflow:
    def install_workflow(self):
        self.legacy_ui = self.takeCentralWidget()
        self.legacy_ui.hide()
        old_left, center, old_right = [self.splitter.widget(i) for i in range(3)]
        narrative = self.right_tabs.widget(0)
        pdf = self.right_tabs.widget(1)
        narrative.setParent(None)
        pdf.setParent(None)
        center.setParent(None)
        self.instructions.setParent(None)
        self.steps_list.setParent(None)
        self.steps_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.add_button.setParent(None)
        self.folder_button.setParent(None)
        self.folder_label.setParent(None)
        self.session_title.setParent(None)
        self.saved_label.setParent(None)
        self.build_button.setParent(None)
        self.export_button.setParent(None)
        self.compiler_label.setParent(None)
        root = QWidget()
        outer = QVBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        header = QFrame()
        header.setObjectName("bar")
        bar = QHBoxLayout(header)
        bar.setContentsMargins(22, 12, 22, 12)
        bar.addWidget(button("Laprak", self.dashboard))
        bar.addWidget(self.session_title, 1)
        bar.addWidget(self.saved_label)
        bar.addWidget(button("Pengaturan lanjutan", self.open_settings))
        outer.addWidget(header)
        nav = QFrame()
        nav.setObjectName("bar")
        nav_layout = QHBoxLayout(nav)
        nav_layout.setContentsMargins(22, 6, 22, 6)
        self.nav_buttons = []
        for index, title in enumerate(("Beranda", "Persiapan", "Dokumentasi", "Periksa laporan", "PDF")):
            action = button(title, lambda checked=False, i=index: self.show_stage(i))
            action.setCheckable(True)
            action.setObjectName("workflowNav")
            self.nav_buttons.append(action)
            nav_layout.addWidget(action)
        nav_layout.addStretch()
        outer.addWidget(nav)
        self.pages = QStackedWidget()
        outer.addWidget(self.pages, 1)

        home, home_layout = page("Laporan praktikum, selangkah demi selangkah", "Siapkan modul, dokumentasikan pekerjaanmu, lalu susun PDF. Pekerjaan tersimpan di perangkat ini.")
        home_layout.addSpacing(18)
        self.new_report_button = button("Buat laporan baru", self.new_session, True)
        home_layout.addWidget(self.new_report_button, alignment=Qt.AlignmentFlag.AlignLeft)
        home_layout.addWidget(button("Buka laporan dari folder", self.open_session), alignment=Qt.AlignmentFlag.AlignLeft)
        home_layout.addSpacing(16)
        home_layout.addWidget(label("Lanjutkan laporan", "section"))
        self.recent_reports = QListWidget()
        self.recent_reports.setObjectName("recentReports")
        self.recent_reports.setMaximumHeight(280)
        self.recent_reports.itemDoubleClicked.connect(lambda *_: self.open_recent())
        home_layout.addWidget(self.recent_reports)
        self.resume_button = button("Lanjutkan laporan terpilih", self.open_recent)
        home_layout.addWidget(self.resume_button, alignment=Qt.AlignmentFlag.AlignLeft)
        extra = QHBoxLayout()
        extra.addWidget(button("Impor proyek ZIP", self.import_project))
        self.duplicate_button = button("Duplikasi laporan aktif", self.duplicate_session)
        extra.addWidget(self.duplicate_button)
        extra.addStretch()
        home_layout.addLayout(extra)
        home_layout.addStretch()
        home_scroll = QScrollArea()
        home_scroll.setWidgetResizable(True)
        home_scroll.setWidget(home)
        self.pages.addWidget(home_scroll)

        setup, setup_layout = page("Persiapkan laporanmu", "Lengkapi satu bagian pada satu waktu. AI dan folder screenshot otomatis bersifat opsional.")
        self.setup_tabs = QHBoxLayout()
        self.setup_buttons = []
        for index, title in enumerate(("Identitas", "Modul", "Template PDF", "AI & screenshot")):
            action = button(f"{index + 1}. {title}", lambda checked=False, i=index: self.show_setup(i))
            action.setCheckable(True)
            action.setObjectName("workflowNav")
            self.setup_buttons.append(action)
            self.setup_tabs.addWidget(action)
        setup_layout.addLayout(self.setup_tabs)
        self.setup_pages = QStackedWidget()
        setup_layout.addWidget(self.setup_pages, 1)
        self.setup_summaries = []
        descriptions = (
            ("Identitas laporan", "Nama, NIM, kelas, dan judul akan dipakai pada sampul laporan.", "Ubah identitas", self.edit_identity),
            ("Panduan dari modul praktikum", "Unggah PDF modul. Periksa daftar tugas sebelum menjadikannya panduan dokumentasi.", "Unggah modul PDF", self.upload_module),
            ("Format laporan dan kesiapan PDF", "Gunakan template LaTeX milikmu. Jika belum siap, dokumentasi tetap bisa dikerjakan.", "Siapkan template & periksa PDF", lambda: self.open_setup_settings(0)),
            ("Bantuan AI, jika kamu membutuhkannya", "Hubungkan GPT melalui browser atau lanjutkan menulis manual. Impor screenshot juga bisa dilakukan langsung di editor.", "Hubungkan GPT", lambda: self.open_setup_settings(1)),
        )
        for index, (title, description, caption, callback) in enumerate(descriptions):
            card, card_layout = page(title, description)
            card.setObjectName("workflowCard")
            summary = label("", "muted")
            summary.setWordWrap(True)
            self.setup_summaries.append(summary)
            card_layout.addWidget(summary)
            card_layout.addWidget(button(caption, callback, True), alignment=Qt.AlignmentFlag.AlignLeft)
            if index == 1:
                card_layout.addWidget(button("Periksa daftar tugas", self.review_module), alignment=Qt.AlignmentFlag.AlignLeft)
                card_layout.addWidget(button("Lihat PDF modul", self.view_module), alignment=Qt.AlignmentFlag.AlignLeft)
            if index == 3:
                card_layout.addSpacing(12)
                card_layout.addWidget(label("Screenshot otomatis", "section"))
                card_layout.addWidget(self.folder_label)
                card_layout.addWidget(self.folder_button, alignment=Qt.AlignmentFlag.AlignLeft)
            card_layout.addStretch()
            self.setup_pages.addWidget(card)
        footer = QHBoxLayout()
        self.setup_back = button("Kembali", lambda: self.show_setup(self.setup_pages.currentIndex() - 1))
        self.setup_next = button("Lanjut", self.next_setup, True)
        footer.addWidget(self.setup_back)
        footer.addStretch()
        footer.addWidget(self.setup_next)
        setup_layout.addLayout(footer)
        setup_scroll = QScrollArea()
        setup_scroll.setWidgetResizable(True)
        setup_scroll.setWidget(setup)
        self.pages.addWidget(setup_scroll)

        document = QWidget()
        document_layout = QVBoxLayout(document)
        document_layout.setContentsMargins(18, 16, 18, 16)
        self.document_hint = label("Pilih langkah → tambahkan screenshot → tulis atau buat draf → periksa dan tandai selesai.", "muted")
        self.document_hint.setWordWrap(True)
        document_heading = QHBoxLayout()
        document_heading.addWidget(self.document_hint, 1)
        self.document_ai_button = button("Hubungkan AI", lambda: self.open_setup_settings(1))
        document_heading.addWidget(self.document_ai_button)
        document_layout.addLayout(document_heading)
        self.document_splitter = QSplitter(Qt.Orientation.Horizontal)
        sidebar = QFrame()
        sidebar.setObjectName("panel")
        sidebar.setMinimumWidth(220)
        sidebar.setMaximumWidth(360)
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(14, 14, 14, 14)
        title_row = QHBoxLayout()
        title_row.addWidget(label("Langkah praktikum", "section"), 1)
        self.add_button.setText("+")
        title_row.addWidget(self.add_button)
        side.addLayout(title_row)
        side.addWidget(self.steps_list, 1)
        self.tasks_toggle = button("Tampilkan tugas dari modul", lambda: self.instructions.setVisible(not self.instructions.isVisible()))
        side.addWidget(self.tasks_toggle)
        self.instructions.setMaximumHeight(200)
        self.instructions.hide()
        self.instructions.setToolTip("Klik tugas untuk menghubungkannya dengan langkah yang sedang dipilih.")
        side.addWidget(self.instructions)
        self.source_label.setParent(None)
        side.addWidget(self.source_label)
        self.document_splitter.addWidget(sidebar)
        self.editor_scroll = QScrollArea()
        self.editor_scroll.setWidgetResizable(True)
        self.editor_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        editor = QWidget()
        editor.setObjectName("documentEditor")
        editor.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        edit_layout = QVBoxLayout(editor)
        edit_layout.setContentsMargins(18, 8, 18, 18)
        edit_layout.setSpacing(16)
        self.image_area.setMinimumHeight(230)
        self.image_area.setMaximumHeight(300)
        self.thumbnails.setMaximumHeight(78)
        self.thumbnails.setIconSize(QSize(76, 46))
        self.thumbnails.setGridSize(QSize(110, 70))
        self.image.setMinimumSize(180, 180)
        center.setMinimumWidth(360)
        self.center_tabs.setTabText(0, "Screenshot")
        self.center_tabs.setTabText(1, "Data yang terbaca")
        self.import_button.setText("Tambahkan screenshot")
        self.analysis_button.setText("Buat draf dengan AI")
        self.analysis_button.setObjectName("primary")
        edit_layout.addWidget(center)
        jump = button("Lanjut ke penjelasan ↓", lambda: self.editor_scroll.ensureWidgetVisible(self.narrative))
        edit_layout.addWidget(jump, alignment=Qt.AlignmentFlag.AlignLeft)
        narrative.setMinimumHeight(350)
        self.narrative.setMinimumHeight(140)
        self.narrative.setMaximumHeight(240)
        self.regenerate_button.setText("Perbarui draf AI")
        self.approve_button.setText("Tandai langkah selesai")
        self.approval_hint = label("", "muted")
        self.approval_hint.setWordWrap(True)
        narrative.layout().insertWidget(narrative.layout().count() - 1, self.approval_hint)
        approval_actions = narrative.layout().takeAt(3).layout()
        narrative.layout().insertLayout(narrative.layout().count() - 1, approval_actions)
        self.notes.setPlaceholderText("Contoh: ping gagal sebelum routing ditambahkan")
        edit_layout.addWidget(narrative)
        narrative.show()
        self.editor_scroll.setWidget(editor)
        self.document_splitter.addWidget(self.editor_scroll)
        self.document_splitter.setSizes([260, 960])
        document_layout.addWidget(self.document_splitter, 1)
        self.pages.addWidget(document)

        review, review_layout = page("Periksa sebelum menyimpan PDF", "Hasil AI tetap draf. Selesaikan kekurangan berikut; hasil pengujian gagal tetap boleh dilaporkan sesuai bukti.")
        self.review_summary = label("", "section")
        review_layout.addWidget(self.review_summary)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        issues = QWidget()
        self.issues_layout = QVBoxLayout(issues)
        scroll.setWidget(issues)
        review_layout.addWidget(scroll, 1)
        actions = QHBoxLayout()
        actions.addWidget(button("Edit pembahasan & bagian laporan", self.report_sections))
        actions.addStretch()
        actions.addWidget(button("Lanjut ke PDF", lambda: self.show_stage(4), True))
        review_layout.addLayout(actions)
        self.pages.addWidget(review)

        pdf_page, pdf_layout = page("PDF laporan", "Buat pratinjau dari pekerjaan terbaru. Simpan PDF final setelah semua pemeriksaan selesai.")
        pdf_actions = QHBoxLayout()
        self.build_button.setText("Buat pratinjau PDF")
        pdf_actions.addWidget(self.build_button)
        self.save_pdf_button = button("Simpan PDF final", self.export_final, True)
        pdf_actions.addWidget(self.save_pdf_button)
        pdf_actions.addWidget(button("Ekspor proyek ZIP", self.export_project))
        pdf_actions.addStretch()
        pdf_layout.addLayout(pdf_actions)
        pdf_layout.addWidget(self.compiler_label)
        self.pdf_fix_button = button("Periksa kesiapan PDF", lambda: self.open_setup_settings(0))
        pdf_layout.addWidget(self.pdf_fix_button, alignment=Qt.AlignmentFlag.AlignLeft)
        pdf_layout.addWidget(pdf, 1)
        pdf.show()
        self.pdf_empty = label("Pratinjau laporan akan muncul di sini.\n\nSiapkan pembuat PDF, lalu klik Buat pratinjau PDF.", "muted")
        self.pdf_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.pdf_empty.setWordWrap(True)
        self.pdf_empty.setMinimumHeight(180)
        self.pdf_empty.setStyleSheet("background: white; border: 1px solid #dfe3e7; border-radius: 8px; padding: 24px;")
        pdf.layout().insertWidget(1, self.pdf_empty, 1)
        self.pdf_review_button = button("Lihat pemeriksaan laporan", lambda: self.show_stage(3))
        pdf_layout.addWidget(self.pdf_review_button, alignment=Qt.AlignmentFlag.AlignLeft)
        self.pages.addWidget(pdf_page)
        self.setCentralWidget(root)
        self.setMinimumSize(800, 480)
        available = self.screen().availableGeometry()
        self.resize(min(1280, available.width() - 24), min(820, available.height() - 24))
        self.show_setup(0)
        self.show_stage(0)

    def dashboard(self):
        self.show_stage(0)

    def show_stage(self, index):
        if index and not self.project:
            index = 0
        self.flush()
        self.pages.setCurrentIndex(index)
        self.statusBar().setVisible(index != 0)
        for i, action in enumerate(self.nav_buttons):
            action.setChecked(i == index)
        if index == 3:
            self.refresh_review()
        if index == 4:
            self.pdf_staleness()
        self.refresh_workflow()

    def show_setup(self, index):
        index = max(0, min(3, index))
        self.setup_pages.setCurrentIndex(index)
        for i, action in enumerate(self.setup_buttons):
            action.setChecked(i == index)
        self.setup_back.setEnabled(index > 0)
        self.setup_next.setText("Mulai dokumentasi" if index == 3 else "Lanjut")

    def next_setup(self):
        if self.setup_pages.currentIndex() == 3:
            self.show_stage(2)
        else:
            self.show_setup(self.setup_pages.currentIndex() + 1)

    def open_recent(self):
        index = self.recent_reports.currentRow()
        if 0 <= index < len(self.recent_paths):
            self.load_project(Path(self.recent_paths[index]))

    def open_setup_settings(self, index):
        self.open_settings(tab=index, simple=True)

    def refresh_workflow(self):
        if not hasattr(self, "pages"):
            return
        enabled = bool(self.project)
        for action in self.nav_buttons[1:]:
            action.setEnabled(enabled)
        self.duplicate_button.setVisible(enabled)
        selected = self.recent_reports.currentRow()
        self.recent_paths = [p for p in self.settings.get("recent", []) if (Path(p) / "session.sqlite").is_file()]
        self.recent_reports.clear()
        self.recent_reports.addItems([Path(p).name + "\n" + p for p in self.recent_paths])
        if self.recent_paths:
            self.recent_reports.setCurrentRow(max(0, min(selected, len(self.recent_paths) - 1)))
        else:
            self.recent_reports.addItem("Belum ada laporan. Mulai dengan Buat laporan baru.")
        self.recent_reports.setFixedHeight(min(240, max(64, len(self.recent_paths) * 66)))
        self.resume_button.setEnabled(bool(self.recent_paths))
        if not enabled:
            return
        identity = self.project.get("identity", {})
        module = self.project.get("module", {})
        self.setup_summaries[0].setText(f"{identity.get('title', '')}\n{identity.get('name', '')} · {identity.get('nim', '')} · {identity.get('class', '')}")
        self.setup_summaries[1].setText((module.get("name", "Belum ada modul PDF")) + "\n" + ("Daftar tugas sudah diperiksa" if self.project.get("module_reviewed") else "Daftar tugas belum diperiksa"))
        self.setup_summaries[2].setText("Template dan pembuat PDF siap digunakan." if self.compiler_ready else "Kesiapan PDF belum diperiksa. Kamu tetap dapat mendokumentasikan praktikum.")
        tested = self.settings.get("capabilities", {}).get(capability_key(self.settings), {})
        ai_status = "AI telah diuji" if tested.get("text") else "Model dipilih · akses belum diuji" if self.settings.get("model") else "Mode manual · AI belum dihubungkan"
        self.status_ai.setText(ai_status)
        self.setup_summaries[3].setText(ai_status)
        has_ai = bool(self.settings.get("model"))
        self.document_ai_button.setVisible(not has_ai)
        self.analysis_button.setEnabled(bool(self.active) and has_ai)
        self.regenerate_button.setEnabled(bool(self.active) and has_ai)
        self.document_hint.setText("Pilih langkah → tambahkan screenshot → tulis atau buat draf → periksa dan tandai selesai." if has_ai else "Mode manual: tambahkan screenshot dan tulis penjelasan. Hubungkan AI jika ingin dibantu membuat draf.")
        self.compiler_label.setText("Pembuat PDF siap" if self.compiler_ready else "Pembuat PDF belum siap · dokumentasi tetap bisa dikerjakan")
        self.pdf_fix_button.setVisible(not self.compiler_ready)
        build = self.project.get("last_build", {})
        has_pdf = self.pdf_document.pageCount() > 0
        self.pdf_view.setVisible(has_pdf)
        self.pdf_empty.setVisible(not has_pdf)
        self.pdf_review_button.setVisible(bool(self.project.blockers()))
        self.save_pdf_button.setEnabled(bool(build) and build.get("revision") == self.project.get("revision", 0) and not self.project.blockers())
        if self.active:
            step = self.project.step(self.active)
            missing = []
            evidence = self.project.evidence(self.active)
            if not evidence:
                missing.append("tambahkan screenshot")
            if not step["narrative"].strip():
                missing.append("isi penjelasan")
            if not all(step["checks"]):
                missing.append("centang kedua pemeriksaan")
            if any(not f.get("reviewed") for f in step["facts"]):
                missing.append("periksa nilai pada tab Data yang terbaca")
            self.approve_button.setEnabled(not missing or bool(step.get("not_applicable", "").strip()))
            self.approval_hint.setText("Agar selesai: " + "; ".join(missing) + "." if missing else "Siap ditandai selesai.")
            self.review_badge.setText("Selesai diperiksa" if step["reviewed"] else "Draf · belum diperiksa")
        if self.pages.currentIndex() == 3:
            self.refresh_review()

    def refresh_review(self):
        if not self.project:
            return
        clear_layout(self.issues_layout)
        issues = []
        module = self.project.get("module")
        if not module:
            issues.append(("Modul belum diunggah", lambda: (self.show_stage(1), self.show_setup(1))))
        elif not self.project.get("module_reviewed"):
            issues.append(("Daftar tugas modul belum diperiksa", self.review_module))
        for step in self.project.steps():
            if step.get("not_applicable", "").strip():
                continue
            if not self.project.evidence(step["id"]):
                issues.append((step["title"] + " · screenshot belum ditambahkan", lambda checked=False, sid=step["id"]: self.review_step(sid)))
            if not step["reviewed"]:
                issues.append((step["title"] + " · penjelasan belum diperiksa", lambda checked=False, sid=step["id"]: self.review_step(sid)))
        for instruction in self.project.get("instructions", []):
            if not any(instruction["id"] in s.get("instruction_ids", []) for s in self.project.steps()):
                issues.append(("Tugas belum dihubungkan: " + instruction["description"], lambda: (self.show_stage(2), self.instructions.show())))
        if not self.project.get("discussion", "").strip() or not self.project.get("conclusion", "").strip():
            issues.append(("Pembahasan atau kesimpulan belum diisi", self.report_sections))
        if not self.project.get("sections_reviewed", False):
            issues.append(("Bagian laporan dan sumbernya belum diperiksa", self.report_sections))
        self.review_summary.setText(f"{len(issues)} hal perlu diselesaikan" if issues else "Pemeriksaan lengkap · laporan siap disimpan setelah PDF dibuat")
        for text, action in issues:
            card = QFrame()
            card.setObjectName("workflowCard")
            card.setMinimumHeight(72)
            line = QHBoxLayout(card)
            caption = QLabel(text)
            caption.setWordWrap(True)
            line.addWidget(caption, 1)
            line.addWidget(button("Perbaiki", action))
            self.issues_layout.addWidget(card)
        self.issues_layout.addStretch()
        self.issues_layout.parentWidget().setMinimumHeight(len(issues) * 80 + 24)

    def review_step(self, identifier):
        self.show_stage(2)
        for index in range(self.steps_list.count()):
            if self.steps_list.item(index).data(Qt.ItemDataRole.UserRole) == identifier:
                self.steps_list.setCurrentRow(index)
                self.editor_scroll.verticalScrollBar().setValue(0)
                break
