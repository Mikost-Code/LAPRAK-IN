import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QDialog
from laprak.app import Workspace, configure_app
from laprak.module_review import ModuleReviewDialog
from laprak.storage import Project


class WorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        configure_app(cls.app)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.window = Workspace(self.root / "data")

    def tearDown(self):
        self.window.close()
        self.app.processEvents()
        self.temp.cleanup()

    def report(self):
        project = Project.create(self.root / "report", {"title": "Pengujian routing", "name": "Uji"})
        project.set("module", {"name": "modul.pdf", "pages": [{"page": 1, "text": "Konfigurasi router", "needs_vision": False}]})
        project.close()
        self.window.load_project(self.root / "report")

    def test_start_is_home_and_other_stages_require_report(self):
        self.assertEqual(self.window.pages.currentIndex(), 0)
        self.window.show_stage(2)
        self.assertEqual(self.window.pages.currentIndex(), 0)
        self.assertTrue(self.window.new_report_button.isEnabled())
        self.assertFalse(self.window.nav_buttons[2].isEnabled())

    def test_manual_documentation_available_without_ai_or_compiler(self):
        self.report()
        self.window.show_setup(3)
        self.window.next_setup()
        self.assertEqual(self.window.pages.currentIndex(), 2)
        self.assertTrue(self.window.narrative.isEnabled())
        self.assertFalse(self.window.build_button.isEnabled())
        self.assertFalse(self.window.approve_button.isEnabled())
        self.assertIn("tambahkan screenshot", self.window.approval_hint.text())

    def test_module_form_approval_creates_mapped_steps_and_preserves_ids(self):
        self.report()
        dialog = ModuleReviewDialog(self.window)
        dialog.add_instruction(instruction={"description": "Konfigurasi router", "page": 1, "evidence": "Modul halaman 1"})
        dialog.approve()
        project = self.window.project
        self.assertTrue(project.get("module_reviewed"))
        identifier = project.get("instructions")[0]["id"]
        self.assertEqual(len(project.steps()), 1)
        self.assertEqual(project.steps()[0]["instruction_ids"], [identifier])
        reopened = ModuleReviewDialog(self.window)
        reopened.approve()
        self.assertEqual(project.get("instructions")[0]["id"], identifier)
        self.assertEqual(len(project.steps()), 1)
        self.window.refresh()
        self.window.show_stage(3)
        self.assertIn("hal perlu diselesaikan", self.window.review_summary.text())
        self.window.resize(880, 500)
        self.window.show()
        self.app.processEvents()
        first_issue = self.window.issues_layout.itemAt(0).widget()
        self.assertGreaterEqual(first_issue.height(), 72)

    def test_invalid_page_cannot_approve_and_edits_survive_closing(self):
        self.report()
        dialog = ModuleReviewDialog(self.window)
        dialog.add_instruction(instruction={"description": "Tugas", "page": 9, "evidence": ""})
        dialog.approve()
        self.assertFalse(self.window.project.get("module_reviewed", False))
        dialog.reject()
        reopened = ModuleReviewDialog(self.window)
        self.assertEqual(reopened.instructions.item(0, 1).text(), "9")
        reopened.reject()

    def test_review_fix_selects_exact_step_without_losing_edits(self):
        self.report()
        identifier = self.window.project.add_step("Uji ping")
        self.window.refresh()
        self.window.narrative.setPlainText("Catatan manual yang harus tersimpan")
        old_identifier = self.window.active
        self.window.show_stage(3)
        self.window.review_step(identifier)
        self.assertEqual(self.window.active, identifier)
        self.assertEqual(self.window.project.step(old_identifier)["narrative"], "Catatan manual yang harus tersimpan")

    def test_new_report_creates_own_folder_without_touching_existing_files(self):
        sentinel = self.root / "existing.txt"
        sentinel.write_text("Keep my file", encoding="utf-8")
        self.window.settings["template"] = str(self.root / "absent-template")
        with patch("laprak.app.IdentityDialog") as identity, patch("laprak.app.QFileDialog.getExistingDirectory", return_value=str(self.root)):
            identity.return_value.exec.return_value = QDialog.DialogCode.Accepted
            identity.return_value.values.return_value = {"title": "Laporan baru", "date": "2026-10-13"}
            self.window.new_session()
        self.assertEqual(sentinel.read_text(encoding="utf-8"), "Keep my file")
        self.assertEqual(self.window.project.root.parent, self.root)
        self.assertNotEqual(self.window.project.root, self.root)
        self.assertEqual(self.window.pages.currentIndex(), 1)
