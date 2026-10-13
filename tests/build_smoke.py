"""Integration check against the supplied template and installed TeX engine."""
import os
import sys
from pathlib import Path
from threading import Event

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PIL import Image, ImageDraw, ImageFont
from PySide6.QtWidgets import QApplication
from PySide6.QtPdf import QPdfDocument
from PySide6.QtCore import QSize
from PySide6.QtGui import QImage, QPainter
from pypdf import PdfReader

from laprak.app import configure_app
from laprak.report import build_report, check_environment, copy_template, detect_compiler
from laprak.storage import Project

root = Path(__file__).resolve().parents[1]
data = root / ".local/build-qa"
data.mkdir(parents=True, exist_ok=True)
project = Project(data / "session") if (data / "session/session.sqlite").exists() else Project.create(data / "session", {
    "title": "Uji Integrasi Template", "name": "Data Pengujian Aplikasi", "nim": "000000000", "class": "RA", "meeting": "1",
    "members": "Data uji aplikasi", "month_year": "Oktober 2026", "assistant_a": "Pengujian", "assistant_b": "Template"})
if not (project.root / "template/main.tex").exists():
    copy_template(root / "template", project.root / "template")
step_id = project.steps()[0]["id"]
project.save_step(step_id, {"title": "Uji karakter khusus dan 50 bukti", "narrative": "Data uji: VLAN_10 & 50% #1 $ {nilai} ~ ^ \\. Pengujian simulasi gagal dan bukan hasil praktikum pengguna.\n\n```cli\nRouter(config)# ip route 192.168.20.0 255.255.255.0 10.0.0.2\nPC0> ping 192.168.20.2\nRequest timed out.\n```"})
if len(project.evidence()) < 50:
    font = ImageFont.truetype("C:/Windows/Fonts/consola.ttf", 24)
    for index in range(50):
        path = data / f"evidence-{index+1:02}.png"
        image = Image.new("RGB", (1000, 520), "#18212a")
        draw = ImageDraw.Draw(image)
        draw.text((32, 28), f"DATA UJI APLIKASI / BUKTI {index+1:02}", fill="#b5dabb", font=font)
        draw.text((32, 100), "PC0 > ping 192.168.20.2\n\nRequest timed out.\nRequest timed out.\n\nSent = 2, Received = 0, Lost = 2 (100% loss)\n\nContoh pengujian gagal, bukan bukti pengguna.", fill="white", font=font)
        image.save(path)
        try:
            project.import_image(path, step_id)
        except FileExistsError:
            pass
compiler = detect_compiler()
checked = check_environment(compiler, "xelatex", project.root / "template", project.root / "build/check", Event())
print("Compiler/template validated:", checked["version"])
snapshot = project.snapshot()
snapshot["discussion"] = "Pengujian integrasi memeriksa escape teks dan batas gambar."
snapshot["conclusion"] = "Ini keluaran uji aplikasi, bukan laporan pengguna."
result = build_report(project.root, snapshot, compiler, Event())
reader = PdfReader(result["pdf"])
assert len(reader.pages) >= 25
assert float(reader.pages[0].mediabox.width) < 510  # B5 remains preserved.
print("Build passed:", len(reader.pages), "pages, 50 evidence images.")
app = QApplication([])
configure_app(app)
document = QPdfDocument()
document.load(result["pdf"])
for page in (0, 1, 3, len(reader.pages)-1):
    image = document.render(page, QSize(704, 1000))
    white = QImage(image.size(), QImage.Format.Format_RGB32)
    white.fill(0xffffffff)
    painter = QPainter(white)
    painter.drawImage(0, 0, image)
    painter.end()
    white.save(str(data / f"page-{page+1}.png"))
document.close()
project.set("last_build", result)
project.export_zip(data / "project.zip")
project.close()
print("PDF QA captures and portable source archive written to .local/build-qa.")
