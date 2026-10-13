"""Render the real redesigned UI using synthetic report data only."""
import os
import sys
import tempfile
from pathlib import Path

scale = sys.argv[1] if len(sys.argv) > 1 else "1"
os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["QT_SCALE_FACTOR"] = scale
from PIL import Image, ImageDraw, ImageFont
from PySide6.QtWidgets import QApplication
from laprak.app import Workspace, configure_app
from laprak.dialogs import SettingsDialog
from laprak.module_review import ModuleReviewDialog
from laprak.storage import Project

app = QApplication([])
configure_app(app)
output = Path(f".local/qa/workflow-{scale}")
output.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(dir=output) as directory:
    root = Path(directory)
    window = Workspace(root / "data")
    window.resize(1280 if scale == "1" else 880, 720 if scale == "1" else 500)
    window.show()
    app.processEvents()
    window.grab().save(str(output / "beranda.png"))
    project = Project.create(root / "report", {"title": "Routing statis", "meeting": "04", "name": "Mahasiswa contoh", "nim": "123456", "class": "RA"})
    project.set("module", {"name": "Modul routing statis.pdf", "pages": [{"page": 1, "text": "Konfigurasi IP dan uji koneksi antar-PC.", "needs_vision": False}]})
    project.close()
    window.load_project(root / "report")
    module = ModuleReviewDialog(window)
    module.add_instruction(instruction={"description": "Konfigurasi alamat IP", "page": 1, "evidence": "Tugas modul"})
    module.add_instruction(instruction={"description": "Uji koneksi antar-PC", "page": 1, "evidence": "Tugas modul"})
    module.show()
    app.processEvents()
    module.grab().save(str(output / "daftar-tugas.png"))
    module.approve()
    window.refresh()
    identifier = window.project.steps()[1]["id"]
    sample = Image.new("RGB", (1000, 350), "#18212a")
    font = ImageFont.truetype("C:/Windows/Fonts/consola.ttf", 28)
    ImageDraw.Draw(sample).text((30, 30), "DATA CONTOH UNTUK AUDIT UI\n\nPC0 > ping 192.168.20.2\nRequest timed out.\n\nHasil: koneksi belum berhasil.", fill="white", font=font)
    image_path = root / "ping-contoh.png"
    sample.save(image_path)
    window.project.import_image(image_path, identifier)
    window.project.save_step(identifier, {"narrative": "Pengujian ping dari PC0 menuju 192.168.20.2 belum berhasil. Bukti memperlihatkan Request timed out. Periksa alamat IP dan konfigurasi routing sebelum menguji ulang.", "notes": "Ping dilakukan setelah konfigurasi alamat IP.", "result": "gagal"})
    window.refresh()
    for index, name in ((1, "persiapan"), (2, "dokumentasi"), (3, "pemeriksaan"), (4, "pdf")):
        window.show_stage(index)
        if index == 1:
            window.show_setup(0)
        if index == 2:
            window.review_step(identifier)
        app.processEvents()
        window.grab().save(str(output / (name + ".png")))
        if index == 2:
            window.editor_scroll.ensureWidgetVisible(window.approve_button)
            app.processEvents()
            window.grab().save(str(output / "penjelasan.png"))
    settings = SettingsDialog(window, {}, window.credentials, window.check_setup)
    settings.simplify(1)
    settings.show()
    app.processEvents()
    settings.grab().save(str(output / "hubungkan-ai.png"))
    settings.close()
    window.close()
    app.processEvents()
print("Workflow rendered at scale", scale)
