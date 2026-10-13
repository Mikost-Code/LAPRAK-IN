import json
import hashlib
from datetime import date
from pathlib import Path

from PySide6.QtCore import Qt, QThreadPool, Signal, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout,
                               QHBoxLayout, QLabel, QLineEdit, QListWidget, QMessageBox, QPushButton,
                               QSpinBox, QTabWidget, QTextEdit, QVBoxLayout, QWidget, QInputDialog, QScrollArea)

from .ai import Adapter, AIError, Analysis, validate_provider_endpoint, credential_profile, is_zen_endpoint
from .report import detect_compiler
from .workers import Worker
from .widgets import ScrollSafeSpinBox, ScrollSafeComboBox


def capability_key(config):
    return hashlib.sha256(json.dumps([config.get(k) for k in ("provider", "endpoint", "model", "structured")]).encode()).hexdigest()


def button(text, callback, primary=False):
    result = QPushButton(text)
    result.setCursor(Qt.CursorShape.PointingHandCursor)
    if primary:
        result.setObjectName("primary")
    result.clicked.connect(callback)
    return result


def label(text, name=""):
    result = QLabel(text)
    result.setObjectName(name)
    return result


FIELDS = [("name", "Nama mahasiswa"), ("nim", "NIM"), ("class", "Kelas"), ("course", "Mata kuliah"),
          ("title", "Judul praktikum"), ("date", "Tanggal (YYYY-MM-DD)"), ("meeting", "Pertemuan"),
          ("month_year", "Bulan dan tahun"), ("assistant_a", "Asisten 1"), ("assistant_b", "Asisten 2"),
          ("members", "Anggota kelompok (satu per baris)")]


class IdentityDialog(QDialog):
    def __init__(self, parent, identity=None):
        super().__init__(parent)
        self.setWindowTitle("Identitas laporan")
        self.setMinimumWidth(510)
        available = self.screen().availableGeometry()
        self.resize(min(640, available.width() - 32), min(700, available.height() - 32))
        layout = QVBoxLayout(self)
        layout.addWidget(label("Identitas praktikum", "heading"))
        fields_page = QWidget()
        form = QFormLayout(fields_page)
        self.identity_form = form
        self.inputs = {}
        months = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus", "September", "Oktober", "November", "Desember"]
        today = date.today()
        defaults = {"course": "Jaringan Komputer", "date": today.isoformat(), "meeting": "1", "month_year": f"{months[today.month-1]} {today.year}"}
        for key, text in FIELDS:
            field = QTextEdit() if key == "members" else QLineEdit()
            if key == "members":
                field.setMaximumHeight(75)
                field.setPlainText((identity or defaults).get(key, ""))
            else:
                field.setText((identity or defaults).get(key, ""))
            self.inputs[key] = field
            form.addRow(text, field)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(fields_page)
        layout.addWidget(scroll, 1)
        extras = ["month_year", "assistant_a", "assistant_b", "members"]
        for key in extras:
            form.setRowVisible(self.inputs[key], False)
        toggle = QCheckBox("Isi identitas tambahan sesuai template")
        toggle.setChecked(any((identity or {}).get(key) for key in extras))
        for key in extras:
            form.setRowVisible(self.inputs[key], toggle.isChecked())
        toggle.toggled.connect(lambda checked: [form.setRowVisible(self.inputs[key], checked) for key in extras])
        layout.addWidget(toggle)
        controls = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Save)
        controls.accepted.connect(self.save)
        controls.button(QDialogButtonBox.StandardButton.Save).setText("Simpan identitas" if identity else "Lanjut · pilih lokasi laporan")
        controls.button(QDialogButtonBox.StandardButton.Save).setObjectName("primary")
        controls.button(QDialogButtonBox.StandardButton.Cancel).setText("Batal")
        controls.rejected.connect(self.reject)
        layout.addWidget(controls)

    def save(self):
        if not self.inputs["title"].text().strip():
            QMessageBox.information(self, "Judul diperlukan", "Isi judul praktikum terlebih dahulu.")
            return
        try:
            date.fromisoformat(self.inputs["date"].text())
        except ValueError:
            QMessageBox.information(self, "Tanggal", "Gunakan tanggal YYYY-MM-DD.")
            return
        self.accept()

    def values(self):
        return {k: v.toPlainText().strip() if isinstance(v, QTextEdit) else v.text().strip() for k, v in self.inputs.items()}


class SettingsDialog(QDialog):
    browser_requested = Signal(str)

    def __init__(self, parent, settings, credentials, check):
        super().__init__(parent)
        self.settings = settings
        self.repaired_zen = settings.get("provider") == "OpenCode" and is_zen_endpoint(settings.get("endpoint", ""))
        self.removed_opencode = settings.get("provider") == "OpenCode" and not self.repaired_zen
        if self.repaired_zen:
            self.settings = settings = dict(settings, provider="OpenCode Zen (API)", structured="Prompt JSON", vision=False)
            if settings.get("model") == "free" or "/" in settings.get("model", ""):
                settings["model"] = ""
        elif self.removed_opencode:
            self.settings = settings = dict(settings, provider="API kompatibel OpenAI", endpoint="https://api.openai.com/v1",
                                             model="", structured="JSON", vision=False)
        self.credentials = credentials
        self.worker = None
        self.browser_requested.connect(self.open_login_browser)
        self.vision_validated = False
        self.setWindowTitle("Setup lingkungan dan AI")
        self.setObjectName("settingsDialog")
        screen = self.screen()
        available = screen.availableGeometry() if screen else None
        self.resize(min(740, available.width() - 60) if available else 740,
                    min(660, available.height() - 60) if available else 660)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 18)
        layout.setSpacing(12)
        layout.addWidget(label("Pengaturan Laprak", "heading"))
        layout.addWidget(label("Compiler dan AI diperiksa secara terpisah.", "muted"))
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)
        environment = QWidget()
        environment.setObjectName("settingsPage")
        environment.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        form = QFormLayout(environment)
        self.environment_form = form
        form.setContentsMargins(20, 20, 20, 20)
        form.setVerticalSpacing(14)
        self.engine = ScrollSafeComboBox()
        self.engine.addItems(["xelatex", "lualatex", "pdflatex"])
        self.engine.setCurrentText(settings.get("engine", "xelatex"))
        self.compiler = QLineEdit(settings.get("compiler", detect_compiler(self.engine.currentText())))
        compiler_row = QHBoxLayout()
        self.compiler_row = compiler_row
        compiler_row.addWidget(self.compiler)
        compiler_row.addWidget(button("Pilih…", self.choose_compiler))
        form.addRow("Engine", self.engine)
        form.addRow("Executable", compiler_row)
        self.template = QLineEdit(settings.get("template", str(Path.cwd() / "template")))
        template_row = QHBoxLayout()
        template_row.addWidget(self.template)
        template_row.addWidget(button("Pilih…", self.choose_template))
        form.addRow("Folder template", template_row)
        form.addRow(label("Template disalin ke sesi. Adaptasi ITERA tersedia; template lain membutuhkan manifest.", "muted"))
        form.addRow(button("Periksa compiler & template", lambda: check(self.values(), self)))
        self.check_status = QLabel("Belum diperiksa dalam peluncuran ini.")
        self.check_status.setWordWrap(True)
        form.addRow(self.check_status)
        install = QLabel('<a href="https://miktex.org/download">Panduan MiKTeX</a> · <a href="https://tug.org/texlive/">TeX Live</a>')
        install.setOpenExternalLinks(True)
        form.addRow(install)
        self.tabs.addTab(environment, "Compiler dan template")
        ai_page = QWidget()
        ai_page.setObjectName("settingsPage")
        ai_page.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        ai_form = QFormLayout(ai_page)
        self.ai_form = ai_form
        ai_form.setContentsMargins(20, 18, 20, 20)
        ai_form.setVerticalSpacing(12)
        ai_form.setHorizontalSpacing(20)
        ai_form.addRow(label("Koneksi AI", "section"))
        self.provider = ScrollSafeComboBox()
        self.provider.addItems(["GPT (login Codex)", "API kompatibel OpenAI", "Ollama", "OpenCode Zen (API)"])
        self.provider.setCurrentText(settings.get("provider", "API kompatibel OpenAI"))
        self.endpoint = QLineEdit(settings.get("endpoint", "https://api.openai.com/v1"))
        self.model = QLineEdit(settings.get("model", ""))
        self.model.setPlaceholderText("Nama model dari provider yang kamu gunakan")
        self.secret = QLineEdit()
        self.secret.setEchoMode(QLineEdit.EchoMode.Password)
        self.secret.setPlaceholderText("Kosong berarti memakai kredensial yang sudah tersimpan")
        self.secret_label = QLabel("API key")
        self.models_button = button("Pilih model…", self.fetch_models)
        self.provider_hint = label("", "muted")
        self.provider_hint.setWordWrap(True)
        self.connect_button = button("Connect GPT", self.connect_gpt, True)
        self.cancel_login_button = button("Batalkan login", self.cancel_login)
        self.cancel_login_button.setVisible(False)
        self.structured = ScrollSafeComboBox()
        self.structured.addItems(["JSON", "JSON schema", "Prompt JSON"])
        self.structured.setCurrentText(settings.get("structured", "JSON"))
        self.timeout = ScrollSafeSpinBox()
        self.timeout.setRange(10, 300)
        self.timeout.setValue(settings.get("timeout", 90))
        self.timeout.setSuffix(" detik")
        self.image_size = ScrollSafeSpinBox()
        self.image_size.setRange(512, 4096)
        self.image_size.setValue(settings.get("image_size", 1600))
        self.image_size.setSuffix(" px")
        self.max_jobs = ScrollSafeSpinBox()
        self.max_jobs.setRange(1, 100)
        self.max_jobs.setValue(settings.get("max_jobs", 10))
        self.vision = QCheckBox("Model mendukung gambar (uji sebelum dipakai)")
        self.vision.setChecked(settings.get("vision", False))
        self.auto = QCheckBox("Analisis otomatis saat screenshot masuk")
        self.auto.setChecked(settings.get("auto", False))
        for text, widget in (("Provider", self.provider), ("Alamat server / API", self.endpoint)):
            ai_form.addRow(text, widget)
        self.endpoint_label = ai_form.labelForField(self.endpoint)
        ai_form.addRow(self.secret_label, self.secret)
        model_row = QHBoxLayout()
        model_row.setSpacing(8)
        model_row.addWidget(self.model, 1)
        model_row.addWidget(self.models_button)
        ai_form.addRow("Model", model_row)
        self.model_row = model_row
        ai_form.addRow(self.provider_hint)
        ai_form.addRow(self.connect_button)
        ai_form.addRow(self.cancel_login_button)
        ai_form.addRow(label("Analisis & pemeriksaan", "section"))
        ai_form.addRow(self.vision)
        ai_form.addRow(self.auto)
        notice = label("AI menerima materi yang dipilih dan konteks langkah. Hasilnya menjadi draf untuk diperiksa. Kredensial disimpan di Credential Manager bila tersedia.", "muted")
        notice.setWordWrap(True)
        ai_form.addRow(notice)
        self.test_button = button("Uji koneksi AI", self.test_connection)
        self.test_status = QLabel("Uji memakai data contoh, tanpa mengirim modul atau gambar pengguna.")
        self.test_status.setWordWrap(True)
        ai_scroll = QScrollArea()
        self.ai_scroll = ai_scroll
        ai_scroll.viewport().setObjectName("settingsViewport")
        ai_scroll.viewport().setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        ai_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        ai_scroll.setWidgetResizable(True)
        ai_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        ai_scroll.setWidget(ai_page)
        self.tabs.addTab(ai_scroll, "Provider AI")
        limits = QWidget()
        limits.setObjectName("settingsPage")
        limits.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        limit_form = QFormLayout(limits)
        limit_form.setContentsMargins(20, 20, 20, 20)
        limit_form.setVerticalSpacing(14)
        limit_form.addRow(label("Keluaran & batas AI", "section"))
        for text, widget in (("Format keluaran", self.structured), ("Waktu tunggu", self.timeout),
                             ("Ukuran gambar maksimum", self.image_size), ("Batas antrean", self.max_jobs)):
            limit_form.addRow(text, widget)
        limit_form.addRow(label("Batas dokumen", "section"))
        self.pdf_mb = ScrollSafeSpinBox()
        self.pdf_mb.setRange(1, 200)
        self.pdf_mb.setValue(settings.get("pdf_mb", 50))
        self.pdf_mb.setSuffix(" MB")
        self.pdf_pages = ScrollSafeSpinBox()
        self.pdf_pages.setRange(1, 1000)
        self.pdf_pages.setValue(settings.get("pdf_pages", 200))
        self.pdf_pages.setSuffix(" halaman")
        limit_form.addRow("Ukuran modul", self.pdf_mb)
        limit_form.addRow("Batas halaman", self.pdf_pages)
        advanced_scroll = QScrollArea()
        self.advanced_scroll = advanced_scroll
        advanced_scroll.viewport().setObjectName("settingsViewport")
        advanced_scroll.viewport().setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        advanced_scroll.setWidgetResizable(True)
        advanced_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        advanced_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        advanced_scroll.setWidget(limits)
        self.tabs.addTab(advanced_scroll, "Lanjutan")
        self.provider.currentTextChanged.connect(self.provider_changed)
        self.update_provider_ui()
        layout.addWidget(self.test_status)
        self.test_status.setObjectName("connectionStatus")
        if self.repaired_zen:
            self.test_status.setText("Alamat Zen terdeteksi: pilihan diperbaiki ke OpenCode Zen (API). Isi API key Zen dan klik Pilih model, lalu Uji koneksi AI.")
        if self.removed_opencode:
            self.test_status.setText("Dukungan server OpenCode lokal sudah dihapus. Pilih ulang provider (Codex, Ollama, API kompatibel OpenAI, atau Zen API), lalu uji koneksi.")
        if self.provider.currentText() == "OpenCode Zen (API)":
            from .zen import is_free_model
            if is_free_model(self.model.text()):
                self.test_status.setText("Model gratis Zen tidak didukung Laprak. Pilih model API berbayar, atau gunakan provider lain.")
        controls = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Save)
        controls.button(QDialogButtonBox.StandardButton.Save).setText("Simpan pengaturan")
        controls.button(QDialogButtonBox.StandardButton.Save).setObjectName("primary")
        controls.button(QDialogButtonBox.StandardButton.Cancel).setText("Batal")
        controls.accepted.connect(self.save)
        controls.rejected.connect(self.reject)
        footer = QHBoxLayout()
        footer.addWidget(self.test_button)
        footer.addStretch()
        footer.addWidget(controls)
        layout.addLayout(footer)
        self.test_button.setVisible(self.tabs.currentIndex() == 1)
        self.tabs.currentChanged.connect(lambda index: self.test_button.setVisible(index == 1))
        self.test_status.setVisible(self.tabs.currentIndex() == 1)
        self.tabs.currentChanged.connect(lambda index: self.test_status.setVisible(index == 1))

    def simplify(self, tab):
        self.simple_mode = True
        self.tabs.tabBar().hide()
        self.tabs.setCurrentIndex(tab)
        self.setWindowTitle("Hubungkan AI" if tab == 1 else "Siapkan PDF laporan")
        self.findChild(QLabel, "heading").setText("Hubungkan GPT" if tab == 1 else "Siapkan PDF laporan")
        self.findChild(QLabel, "muted").setText("Login di browser tanpa memasukkan API key." if tab == 1 else "Pilih format laporan, lalu periksa kesiapan pembuat PDF.")
        self.environment_form.setRowVisible(self.engine, False)
        self.environment_form.setRowVisible(self.compiler_row, False)
        details = button("Tampilkan pengaturan teknis", self.reveal_technical)
        self.environment_form.addRow(details)
        if tab == 1:
            self.provider.setCurrentText("GPT (login Codex)")
            self.ai_form.setRowVisible(self.provider, False)
            self.ai_form.setRowVisible(self.model_row, False)
            self.vision.hide()
            self.test_button.setText("Periksa kemampuan AI")
            self.provider_hint.setText("Masuk melalui browser dengan akun ChatGPT. Kamu dapat kembali ke Laprak setelah login berhasil. Pemakaian mengikuti kuota akunmu.")
            self.ai_form.addRow(button("Pilih provider atau model lain", self.reveal_technical))
        self.findChild(QDialogButtonBox).button(QDialogButtonBox.StandardButton.Save).setText("Selesai")

    def reveal_technical(self):
        self.simple_mode = False
        self.tabs.tabBar().show()
        self.environment_form.setRowVisible(self.engine, True)
        self.environment_form.setRowVisible(self.compiler_row, True)
        self.ai_form.setRowVisible(self.provider, True)
        self.ai_form.setRowVisible(self.model_row, True)
        self.vision.show()

    def provider_changed(self, provider):
        self.endpoint.setText({"Ollama": "http://localhost:11434", "OpenCode Zen (API)": "https://opencode.ai/zen/v1"}.get(provider, "https://api.openai.com/v1"))
        self.vision.setChecked(False)
        self.secret.clear()
        self.model.clear()
        if provider == "OpenCode Zen (API)":
            self.structured.setCurrentText("Prompt JSON")
        self.update_provider_ui()
        self.test_status.setText("Pilih model dan jalankan Uji koneksi AI. Pengujian dapat memakai kuota provider.")
        if provider == "GPT (login Codex)":
            self.endpoint.setText("codex://local")
            self.structured.setCurrentText("Prompt JSON")
            self.test_status.setText("Klik Connect GPT, login di browser, kemudian kembali ke Laprak. Tidak perlu API key.")

    def update_provider_ui(self):
        codex = self.provider.currentText() == "GPT (login Codex)"
        zen = self.provider.currentText() == "OpenCode Zen (API)"
        self.models_button.setVisible(zen or codex)
        self.provider_hint.setVisible(zen or codex)
        self.connect_button.setVisible(True)
        for widget in (self.endpoint, self.endpoint_label, self.secret, self.secret_label):
            widget.setVisible(not codex)
        if zen:
            self.provider_hint.setText("API langsung Zen hanya menawarkan model Chat Completions berbayar; model gratis tidak didukung Laprak. Pemanggilan dapat memakai saldo akun.")
        elif codex:
            self.provider_hint.setText("Klik Connect GPT untuk masuk melalui halaman resmi Codex di browser. Setelah berhasil, kembali ke Laprak; model dipilih otomatis. Pemakaian mengikuti akses dan kuota akun ChatGPT. Codex CLI harus terpasang.")
        self.secret.setPlaceholderText("API key provider, atau kosong jika sudah tersimpan")
        self.model.setPlaceholderText("ID model Zen (klik Pilih model)" if zen else "Nama model dari provider")
        if codex:
            self.model.setPlaceholderText("Dipilih otomatis setelah login")

    def connect_gpt(self):
        if self.worker:
            return
        self.provider.setCurrentText("GPT (login Codex)")
        from .codex import login
        self.login_active = True
        self.connect_button.setEnabled(False)
        self.test_button.setEnabled(False)
        self.models_button.setEnabled(False)
        self.provider.setEnabled(False)
        self.cancel_login_button.setVisible(True)
        self.test_status.setText("Menyiapkan login Codex…")
        self.worker = Worker(lambda cancel: login(self.browser_requested.emit, cancel))
        self.worker.signals.done.connect(self.login_done)
        self.worker.signals.failed.connect(self.test_failed)
        QThreadPool.globalInstance().start(self.worker)

    def open_login_browser(self, url):
        if not getattr(self, "login_active", False) or not self.worker or self.worker.cancel.is_set():
            return
        if not QDesktopServices.openUrl(QUrl(url)):
            self.worker.cancel.set()
            self.test_status.setText("Browser tidak dapat dibuka. Atur browser default lalu coba Connect GPT kembali.")
            return
        self.test_status.setText("Browser sudah dibuka. Selesaikan login Codex, lalu kembali ke Laprak. Keberhasilan akan terdeteksi otomatis.")

    def reset_login_ui(self):
        self.login_active = False
        self.connect_button.setEnabled(True)
        self.provider.setEnabled(True)
        self.cancel_login_button.setVisible(False)

    def cancel_login(self):
        if self.worker:
            self.worker.cancel.set()
            self.test_status.setText("Membatalkan login…")

    def login_done(self, model):
        self.worker = None
        self.reset_login_ui()
        self.test_button.setEnabled(True)
        self.models_button.setEnabled(True)
        self.model.setText(model)
        self.endpoint.setText("codex://local")
        self.test_status.setText("Login berhasil! Kembali ke Laprak dan klik Simpan pengaturan. GPT sudah terhubung; Uji koneksi AI untuk memeriksa akses model.")
        self.raise_()
        self.activateWindow()

    def fetch_models(self):
        if self.worker:
            return
        from .zen import Zen
        from .codex import Codex
        config = self.values()
        try:
            adapter_class = Codex if config["provider"] == "GPT (login Codex)" else Zen
            adapter = adapter_class(config, self.secret.text() or self.credentials.get(self.profile()))
        except ValueError as error:
            self.test_status.setText(str(error))
            return
        self.models_button.setEnabled(False)
        self.test_button.setEnabled(False)
        self.models_config = config
        self.test_status.setText("Mengambil daftar model…")
        self.worker = Worker(lambda cancel: adapter.models())
        self.worker.signals.done.connect(self.models_done)
        self.worker.signals.failed.connect(self.test_failed)
        QThreadPool.globalInstance().start(self.worker)

    def models_done(self, models):
        self.worker = None
        self.models_button.setEnabled(True)
        self.test_button.setEnabled(True)
        if any(self.values().get(key) != self.models_config.get(key) for key in ("provider", "endpoint")):
            self.test_status.setText("Pengaturan berubah; ambil ulang daftar model.")
            return
        self.test_status.setText(f"{len(models)} model tersedia. Uji kemampuan setelah memilih model.")
        if not models:
            self.test_status.setText("Belum ada model yang tersedia. Periksa login provider atau koneksi server.")
            return
        index = models.index(self.model.text()) if self.model.text() in models else 0
        model, accepted = QInputDialog.getItem(self, "Pilih model AI", "Model", models, index, False)
        if accepted:
            self.model.setText(model)
            self.vision.setChecked(False)

    def choose_compiler(self):
        path, _ = QFileDialog.getOpenFileName(self, "Pilih compiler", "", "Executable (*.exe)")
        if path:
            self.compiler.setText(path)

    def choose_template(self):
        path = QFileDialog.getExistingDirectory(self, "Pilih folder template")
        if path:
            self.template.setText(path)

    def values(self):
        return dict(self.settings, engine=self.engine.currentText(), compiler=self.compiler.text().strip(), template=self.template.text().strip(),
                    provider=self.provider.currentText(), endpoint=self.endpoint.text().strip(), model=self.model.text().strip(),
                    structured=self.structured.currentText(), timeout=self.timeout.value(), image_size=self.image_size.value(),
                    max_jobs=self.max_jobs.value(), vision=self.vision.isChecked(), auto=self.auto.isChecked(),
                    pdf_mb=self.pdf_mb.value(), pdf_pages=self.pdf_pages.value())

    def profile(self):
        return credential_profile(self.values())

    def save(self):
        if self.worker:
            self.test_status.setText("Tunggu proses selesai atau batalkan login sebelum menyimpan.")
            return
        try:
            validate_provider_endpoint(self.values())
        except ValueError as error:
            QMessageBox.warning(self, "Endpoint", str(error))
            return
        config = self.values()
        if config["provider"] == "GPT (login Codex)" and not config["model"]:
            self.tabs.setCurrentIndex(1)
            self.test_status.setText("Klik Connect GPT terlebih dahulu agar model dipilih otomatis.")
            return
        if config["provider"] == "OpenCode Zen (API)":
            from .zen import validate_model
            try:
                validate_model(config["model"])
            except AIError as error:
                self.test_status.setText(str(error))
                self.tabs.setCurrentIndex(1)
                return
            if not (self.secret.text() or self.credentials.get(self.profile())):
                self.test_status.setText("Isi API key Zen sebelum menyimpan.")
                self.tabs.setCurrentIndex(1)
                return
        tested = self.settings.get("capabilities", {})
        if self.vision.isChecked() and not tested.get(capability_key(config), {}).get("vision"):
            QMessageBox.information(self, "Uji vision diperlukan", "Jalankan Uji koneksi & kemampuan dengan opsi gambar aktif. Dukungan gambar harus terverifikasi untuk model ini.")
            return
        if self.secret.text():
            if not self.credentials.put(self.profile(), self.secret.text()):
                QMessageBox.information(self, "Kredensial sesi", "Credential Manager tidak tersedia; kredensial hanya disimpan di memori sampai aplikasi ditutup.")
        self.accept()

    def test_connection(self):
        if self.worker:
            return
        config = self.values()
        if getattr(self, "simple_mode", False):
            config["vision"] = True
        secret = self.secret.text() or self.credentials.get(self.profile())
        try:
            adapter = Adapter(config, secret)
        except ValueError as error:
            self.test_status.setText(str(error))
            return
        self.test_button.setEnabled(False)
        self.models_button.setEnabled(False)
        self.test_status.setText("Menguji JSON dan kemampuan model…")
        self.test_config = config
        def run(cancel):
            adapter.run('Uji: tulis narrative="Koneksi berhasil"; facts=[], unknown=[], result="belum diketahui".', cancel=cancel)
            result = {"text": True, "vision": False}
            if config["vision"]:
                from PIL import Image, ImageDraw, ImageFont
                import tempfile
                import secrets
                code = secrets.token_hex(3).upper()
                image = Image.new("RGB", (800, 200), "white")
                font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 72)
                ImageDraw.Draw(image).text((30, 55), code, fill="black", font=font)
                with tempfile.TemporaryDirectory() as folder:
                    path = Path(folder) / "vision-test.png"
                    image.save(path)
                    try:
                        response = adapter.run("Baca kode yang terlihat pada gambar. Isi narrative hanya dengan kode tersebut, facts=[], unknown=[], result='belum diketahui'.", images=[path], cancel=cancel)
                        result["vision"] = code == response["narrative"].strip()
                    except AIError:
                        if not getattr(self, "simple_mode", False) or cancel.is_set():
                            raise
            return result
        self.worker = Worker(run)
        self.worker.signals.done.connect(self.test_done)
        self.worker.signals.failed.connect(self.test_failed)
        QThreadPool.globalInstance().start(self.worker)

    def test_done(self, result):
        self.test_button.setEnabled(True)
        self.models_button.setEnabled(True)
        self.settings.setdefault("capabilities", {})[capability_key(self.test_config)] = result
        self.worker = None
        if capability_key(self.values()) != capability_key(self.test_config):
            self.test_status.setText("Pengaturan berubah saat pengujian. Uji ulang model yang sekarang dipilih.")
            return
        self.test_status.setText("Text dan JSON berhasil. " + ("Vision berhasil membaca kode gambar contoh." if result["vision"] else "Vision belum berhasil diuji; gunakan mode teks/manual."))
        self.vision.setChecked(result["vision"])
        self.settings["text_tested"] = True

    def test_failed(self, error):
        self.reset_login_ui()
        self.test_button.setEnabled(True)
        self.models_button.setEnabled(True)
        self.test_status.setText(str(error))
        self.worker = None

    def reject(self):
        if self.worker:
            self.worker.cancel.set()
        super().reject()


class TextDialog(QDialog):
    def __init__(self, parent, title, text, hint=""):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(720, 620)
        layout = QVBoxLayout(self)
        layout.addWidget(label(title, "heading"))
        if hint:
            hint_label = label(hint, "muted")
            hint_label.setWordWrap(True)
            layout.addWidget(hint_label)
        self.editor = QTextEdit()
        self.editor.setAcceptRichText(False)
        self.editor.setPlainText(text)
        layout.addWidget(self.editor)
        controls = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Save)
        controls.accepted.connect(self.accept)
        controls.rejected.connect(self.reject)
        layout.addWidget(controls)
