"""Real Chromium + React + QWebChannel smoke, using synthetic local reports."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import json
from pathlib import Path
import sys
import tempfile
import time
from unittest.mock import patch

from PIL import Image, ImageDraw, ImageFont
from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtWidgets import QApplication
from laprak.desktop import ReactWindow
from laprak.storage import Project


def javascript(window, code, timeout=3000):
    loop = QEventLoop()
    result = []
    def done(value):
        result.append(value)
        loop.quit()
    window.page.runJavaScript(code, done)
    QTimer.singleShot(timeout, loop.quit)
    loop.exec()
    return result[0] if result else None


def until(window, predicate, timeout=15):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if javascript(window, predicate):
            return
        loop = QEventLoop()
        QTimer.singleShot(100, loop.quit)
        loop.exec()
    raise AssertionError(f"React condition timed out: {predicate}; errors={window.page.errors}")


def smoke(window, output):
    def capture(name):
        loop = QEventLoop()
        QTimer.singleShot(500, loop.quit)
        loop.exec()
        window.grab().save(str(output / name))
    window.show()
    until(window, "!!window.laprakReady")
    until(window, "document.querySelector('.welcome-card')?.getBoundingClientRect().height > 0")
    capture("react-home.png")
    assert "Dari praktikum" in javascript(window, "document.body.innerText")
    if window.backend.project:
        javascript(window, "[...document.querySelectorAll('.nav-item')].find(b=>b.textContent.includes('Dokumentasi')).click()")
        until(window, "!!document.querySelector('.step-editor')")
        until(window, "!!document.querySelector('.image-canvas img')?.naturalWidth")
        capture("react-editor.png")
        javascript(window, "document.querySelector('.narrative-input').scrollIntoView({block:'center'})")
        capture("react-narrative.png")
        javascript(window, "(()=>{const field=document.querySelector('.narrative-input');Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype,'value').set.call(field,'Autosave React terverifikasi');field.dispatchEvent(new Event('input',{bubbles:true}));})()")
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and window.backend.project.step(window.backend.active)["narrative"] != "Autosave React terverifikasi":
            loop = QEventLoop()
            QTimer.singleShot(100, loop.quit)
            loop.exec()
        assert window.backend.project.step(window.backend.active)["narrative"] == "Autosave React terverifikasi"
        javascript(window, "(()=>{const field=document.querySelector('.narrative-input');Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype,'value').set.call(field,'Edit sebelum berpindah halaman');field.dispatchEvent(new Event('input',{bubbles:true}));})()")
        javascript(window, "[...document.querySelectorAll('.nav-item')].find(b=>b.textContent.includes('Periksa laporan')).click()")
        until(window, "!!document.querySelector('.review-list')")
        assert window.backend.project.step(window.backend.active)["narrative"] == "Edit sebelum berpindah halaman"
        capture("react-review.png")
        window.resize(900, 650)
        until(window, "window.innerWidth < 1000")
        assert javascript(window, "document.documentElement.scrollWidth <= window.innerWidth+1"), "Horizontal overflow on laptop width"
        capture("react-laptop.png")
        window.resize(1366, 850)
    assert not window.page.errors, window.page.errors
    return {"startup": True, "react": True, "bridge": True, "qt_pdf": window.backend.pdf_document is not None, "frozen": bool(getattr(sys, "frozen", False))}


if __name__ == "__main__":
    output = Path(".local/react-qa")
    output.mkdir(parents=True, exist_ok=True)
    app = QApplication([])
    with tempfile.TemporaryDirectory(dir=output) as directory:
        root = Path(directory)
        project = Project.create(root / "report", {"title": "Routing statis", "meeting": "04", "name": "Mahasiswa contoh", "nim": "123456", "class": "RA"})
        identifier = project.steps()[0]["id"]
        image = Image.new("RGB", (1000, 350), "#18212a")
        ImageDraw.Draw(image).text((35, 30), "DATA CONTOH UNTUK PENGUJIAN UI\n\nPC0 > ping 192.168.20.2\nRequest timed out.\n\nKoneksi belum berhasil.", fill="white", font=ImageFont.truetype("C:/Windows/Fonts/consola.ttf", 28))
        path = root / "ping-contoh.png"
        image.save(path)
        project.import_image(path, identifier)
        project.save_step(identifier, {"title": "Uji koneksi antar-PC", "narrative": "Pengujian ping menuju 192.168.20.2 belum berhasil. Bukti memperlihatkan Request timed out. Periksa konfigurasi sebelum mencoba kembali.", "notes": "Ping dilakukan setelah konfigurasi IP.", "result": "gagal"})
        project.close()
        window = ReactWindow(root / "data")
        window.resize(1366, 850)
        window.backend.load_project(root / "report")
        try:
            result = smoke(window, output)
            javascript(window, "[...document.querySelectorAll('.nav-item')].find(b=>b.textContent.includes('Dokumentasi')).click()")
            until(window, "!!document.querySelector('.narrative-input')")
            javascript(window, "(()=>{const field=document.querySelector('.narrative-input');Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype,'value').set.call(field,'Edit terakhir sebelum menutup');field.dispatchEvent(new Event('input',{bubbles:true}));})()")
            window.close()
            deadline = time.monotonic() + 8
            while window.isVisible() and time.monotonic() < deadline:
                loop = QEventLoop()
                QTimer.singleShot(100, loop.quit)
                loop.exec()
            assert not window.isVisible(), "Native close handshake did not complete"
            import sqlite3
            with sqlite3.connect(root / "report/session.sqlite") as connection:
                saved = json.loads(connection.execute("SELECT data FROM steps WHERE id=?", (identifier,)).fetchone()[0])
                assert saved["narrative"] == "Edit terakhir sebelum menutup"
            connection.close()
            result["close_flush"] = True
            (output / "result.json").write_text(json.dumps(result), encoding="utf-8")
        finally:
            window.close_allowed = True
            window.close()
            app.processEvents()
    print("React + Chromium + Python bridge smoke passed.")
