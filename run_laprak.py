import json
import os
import sys
from pathlib import Path

from laprak.app import Workspace, configure_app, main

if __name__ == "__main__":
    if "--verify-bundle" in sys.argv:
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        from PySide6.QtWidgets import QApplication
        application = QApplication([])
        configure_app(application)
        directory = Path.cwd() / ".local/bundle-qa"
        workspace = Workspace(directory)
        workspace.show()
        application.processEvents()
        workspace.grab().save(str(directory / "workspace.png"))
        (directory / "result.json").write_text(json.dumps({"startup": True, "qt_pdf": workspace.pdf_document is not None, "frozen": bool(getattr(sys, "frozen", False))}), encoding="utf-8")
        workspace.close()
    else:
        main()
