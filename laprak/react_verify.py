"""Frozen-build startup check for the actual React renderer and local bridge."""
import json
from pathlib import Path
import sys
import time
from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtWidgets import QApplication
from .desktop import ReactWindow


def verify(directory):
    app = QApplication.instance() or QApplication([])
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    window = ReactWindow(directory)
    window.resize(1280, 800)
    window.show()
    ready = False
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        loop = QEventLoop()
        result = []
        window.page.runJavaScript("!!window.laprakReady && !!document.querySelector('.welcome-card')", lambda value: (result.append(bool(value)), loop.quit()))
        QTimer.singleShot(1000, loop.quit)
        loop.exec()
        if result and result[0]:
            ready = True
            break
    if not ready:
        window.close_allowed = True
        window.close()
        raise RuntimeError("React renderer / bridge did not initialize")
    loop = QEventLoop()
    QTimer.singleShot(700, loop.quit)
    loop.exec()
    window.grab().save(str(directory / "workspace.png"))
    result = {"startup": True, "react": True, "bridge": True, "qt_pdf": window.backend.pdf_document is not None,
              "frozen": bool(getattr(sys, "frozen", False)), "javascript_errors": window.page.errors}
    (directory / "result.json").write_text(json.dumps(result), encoding="utf-8")
    window.close_allowed = True
    window.close()
    app.processEvents()
