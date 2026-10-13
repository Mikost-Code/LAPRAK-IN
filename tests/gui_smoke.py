"""Runs Qt offscreen, verifies editing/restore/AI stale response behavior and saves a QA capture."""
import json
import os
import sys
import time
import uuid
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication
from PIL import Image, ImageDraw, ImageFont

from laprak.app import Workspace, configure_app
from laprak.report import copy_template
from laprak.storage import Project
from laprak.style import STYLE

root = Path(__file__).resolve().parents[1]
data = root / ".local/qa"
data.mkdir(parents=True, exist_ok=True)
app = QApplication([])
configure_app(app)
session_path = data / "session"
if not (session_path / "session.sqlite").exists():
    project = Project.create(session_path, {"title": "Routing Statis", "meeting": "04", "name": "Mahasiswa", "nim": "123", "class": "RA"})
    copy_template(root / "template", project.root / "template")
    for title in ("Konfigurasi IP", "Routing statis", "Uji koneksi", "Tugas tambahan"):
        project.add_step(title)
    project.close()
window = Workspace(data)
window.load_project(session_path)
window.show()
app.processEvents()
assert window.active
window.steps_list.setCurrentRow(3)
app.processEvents()
window.notes.setText("Catatan uji yang tersimpan lokal")
window.narrative.setPlainText("Pengujian belum dilakukan; hasil koneksi belum diketahui.")
window.flush()
assert window.project.step(window.active)["notes"] == "Catatan uji yang tersimpan lokal"
assert window.project.step(window.active)["narrative"].startswith("Pengujian")
job_id = window.project.add_job("generate_explanation", window.active, {"cache_key": "qa", "config": {"model": "test"}})
job = next(j for j in window.project.jobs() if j["id"] == job_id)
window.project.save_step(window.active, {"notes": "Edit baru"})
window.job_done(job, {"facts": [], "narrative": "Respons AI lama", "unknown": [], "result": "belum diketahui"})
assert window.project.step(window.active)["narrative"] != "Respons AI lama"
assert window.project.db.execute("SELECT count(*) FROM revisions WHERE step_id=?", (window.active,)).fetchone()[0] > 0
app.processEvents()
watch_folder = data / "screenshot-input"
watch_folder.mkdir(exist_ok=True)
window.start_watch(watch_folder)
captured_step = window.active
name = "uji-" + uuid.uuid4().hex + ".png"
sample = Image.new("RGB", (1000, 520), "#18212a")
font = ImageFont.truetype("C:/Windows/Fonts/consola.ttf", 24)
ImageDraw.Draw(sample).text((32, 40), "DATA UJI APLIKASI\n\nPC0 > ping 192.168.20.2\n\nRequest timed out.\n\nContoh untuk validasi UI, bukan bukti pengguna.\n" + name, font=font, fill="white")
sample.save(watch_folder / name)
window.watch_event(str(watch_folder / name))
window.steps_list.setCurrentRow(0)
until = time.monotonic()+5
while time.monotonic() < until:
    app.processEvents()
    if any(e["name"] == name for e in window.project.evidence()):
        break
    time.sleep(0.01)
matching = next(e for e in window.project.evidence() if e["name"] == name)
assert matching["step_id"] == captured_step
window.stop_watch()
window.steps_list.setCurrentRow(3)
app.processEvents()
window.grab().save(str(data / "workspace.png"))
window.close()
print("GUI smoke passed: autosave, step selection, stale AI revision, watcher stability/context, screenshot.")
