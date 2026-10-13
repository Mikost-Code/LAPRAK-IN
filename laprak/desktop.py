"""React desktop host. Bundled local HTML communicates over Qt WebChannel."""
import argparse
import json
import os
from pathlib import Path
import sys

# Stable software compositing for desktop/offscreen Windows GPU drivers.
# This does not disable Chromium's process sandbox.
os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--disable-gpu")
os.environ.setdefault("QT_QUICK_BACKEND", "software")

from PySide6.QtCore import QTimer, QUrl, Qt
from PySide6.QtWidgets import QApplication, QMainWindow, QMessageBox
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineSettings, QWebEngineUrlRequestInterceptor
from PySide6.QtWebEngineWidgets import QWebEngineView

from .react_bridge import BackendWorkspace, ReactBridge


def web_root():
    bundled = Path(__file__).parent / "web"
    return bundled if bundled.is_dir() else Path(__file__).resolve().parents[1] / "frontend/dist"


class LocalRequests(QWebEngineUrlRequestInterceptor):
    def interceptRequest(self, info):
        if info.requestUrl().scheme() in ("http", "https", "ws", "wss"):
            info.block(True)


class LocalPage(QWebEnginePage):
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.errors = []

    def acceptNavigationRequest(self, url, navigation_type, is_main_frame):
        if url.scheme() in ("about", "qrc", "data"):
            return True
        if url.scheme() != "file":
            return False
        path = Path(url.toLocalFile()).resolve()
        if is_main_frame:
            return path.is_relative_to(web_root().resolve())
        project = self.window.backend.project
        return path.is_relative_to(web_root().resolve()) or bool(project and path.is_relative_to(project.root / "output"))

    def javaScriptConsoleMessage(self, level, message, line, source):
        if level == QWebEnginePage.JavaScriptConsoleMessageLevel.ErrorMessageLevel:
            self.errors.append(message)


class ReactWindow(QMainWindow):
    def __init__(self, data_root):
        super().__init__()
        self.setWindowTitle("Laprak — laporan praktikum")
        self.backend = BackendWorkspace(data_root)
        self.backend.hide()
        self.bridge = ReactBridge(self.backend, self)
        self.view = QWebEngineView(self)
        self.page = LocalPage(self)
        self.view.setPage(self.page)
        self.channel = QWebChannel(self.page)
        self.channel.registerObject("laprak", self.bridge)
        self.page.setWebChannel(self.channel)
        self.interceptor = LocalRequests(self.page)
        self.page.profile().setUrlRequestInterceptor(self.interceptor)
        self.page.profile().downloadRequested.connect(lambda download: download.cancel())
        self.page.settings().setAttribute(QWebEngineSettings.WebAttribute.PluginsEnabled, True)
        self.page.settings().setAttribute(QWebEngineSettings.WebAttribute.PdfViewerEnabled, True)
        self.page.settings().setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, False)
        self.page.settings().setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)
        self.setCentralWidget(self.view)
        available = self.screen().availableGeometry()
        self.resize(min(1400, available.width() - 32), min(900, available.height() - 32))
        self.setMinimumSize(780, 500)
        self.close_allowed = False
        self.bridge.close_ready.connect(self.finish_close)
        self.view.load(QUrl.fromLocalFile(str(web_root() / "index.html")))

    def closeEvent(self, event):
        if not self.close_allowed:
            event.ignore()
            self.page.runJavaScript("if(window.laprakFlush){window.laprakFlush()}else if(window.qt){new QWebChannel(qt.webChannelTransport,c=>c.objects.laprak.request(JSON.stringify({id:-1,method:'closeApp'})))}")
            return
        self.backend.closing = True
        self.backend.queue_paused = True
        self.backend.stop_watch()
        self.backend.cancel_tasks()
        self.bridge.timer.stop()
        if self.backend.tasks:
            event.ignore()
            self.hide()
            QTimer.singleShot(100, self.finish_close)
            return
        self.backend.close()
        event.accept()

    def finish_close(self):
        self.close_allowed = True
        self.close()


def main():
    parser = argparse.ArgumentParser(description="Laprak React desktop")
    parser.add_argument("--data-dir", type=Path, default=Path.cwd() / ".local")
    parser.add_argument("--session", type=Path)
    args = parser.parse_args()
    app = QApplication(sys.argv[:1])
    app.setApplicationName("Laprak")
    if not (web_root() / "index.html").is_file():
        QMessageBox.critical(None, "Antarmuka belum dibangun", "Jalankan npm install dan npm run build di folder frontend, lalu buka Laprak kembali.")
        return
    window = ReactWindow(args.data_dir)
    if args.session:
        window.backend.load_project(args.session)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
