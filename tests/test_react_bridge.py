import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image
from PySide6.QtWidgets import QApplication
from laprak.react_bridge import BackendWorkspace, ReactBridge
from laprak.storage import Project


class ReactBridgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.workspace = BackendWorkspace(self.root / "data")
        self.credential_patch = patch.object(self.workspace.credentials, "put", return_value=False)
        self.credential_patch.start()
        self.bridge = ReactBridge(self.workspace)
        p = Project.create(self.root / "report", {"title": "Test report"})
        p.set("module", {"name": "modul.pdf", "pages": [{"page": 1, "text": "Tugas", "needs_vision": False}]})
        p.close()
        self.workspace.load_project(self.root / "report")
        self.identifier = self.workspace.active

    def tearDown(self):
        self.credential_patch.stop()
        self.bridge.timer.stop()
        self.workspace.close()
        self.app.processEvents()
        self.temp.cleanup()

    def test_secrets_never_enter_frontend_state_or_settings(self):
        self.bridge.dispatch("saveSettings", {"provider": "API kompatibel OpenAI", "endpoint": "https://api.openai.com/v1", "model": "example", "secret": "not-a-real-secret"})
        import json
        self.assertNotIn("not-a-real-secret", json.dumps(self.bridge.state()))
        self.assertNotIn("not-a-real-secret", self.workspace.settings_file.read_text())

    def test_save_and_select_do_not_overwrite_react_edits_with_hidden_widgets(self):
        self.bridge.dispatch("saveStep", {"id": self.identifier, "narrative": "New React narrative", "notes": "New note"})
        self.bridge.dispatch("selectStep", {"id": self.identifier})
        self.workspace.flush()
        self.assertEqual(self.workspace.project.step(self.identifier)["narrative"], "New React narrative")

    def test_approval_rejects_new_evidence_since_review(self):
        image = self.root / "test.png"
        Image.new("RGB", (10, 10)).save(image)
        self.workspace.project.import_image(image, self.identifier)
        self.bridge.dispatch("saveStep", {"id": self.identifier, "narrative": "Reviewed evidence"})
        with self.assertRaises(ValueError):
            self.bridge.dispatch("approveStep", {"id": self.identifier, "checks": [True, True], "snapshot": {"narrative": "Reviewed evidence", "facts": [], "evidenceIds": []}})
        self.assertFalse(self.workspace.project.step(self.identifier)["reviewed"])

    def test_module_review_creates_steps_and_preserves_ids(self):
        draft = dict(objectives=[], theory="", tools=[], instructions=[{"description": "Tugas", "page": 1, "evidence": "PDF"}], unknown_pages=[])
        self.bridge.dispatch("saveModule", {"data": draft, "createSteps": True})
        identifier = self.workspace.project.get("instructions")[0]["id"]
        self.bridge.dispatch("saveModule", {"data": draft, "createSteps": True})
        self.assertEqual(self.workspace.project.get("instructions")[0]["id"], identifier)
        self.assertEqual(len(self.workspace.project.steps()), 1)
        self.assertTrue(self.workspace.project.get("module_reviewed"))

    def test_cancel_does_not_start_remaining_queue(self):
        job = self.workspace.project.add_job("generate_explanation", self.identifier, {"cache_key": "example"})
        self.bridge.dispatch("cancel", {})
        self.assertEqual(self.workspace.project.jobs()[0]["status"], "cancelled")
        self.assertTrue(self.workspace.queue_paused)

    def test_draft_module_survives_until_approval(self):
        draft = dict(objectives=[], theory="", tools=[], instructions=[{"description": "Draft", "page": 1, "evidence": ""}], unknown_pages=[])
        self.bridge.dispatch("draftModule", {"data": draft, "source": "Corrected text"})
        self.assertEqual(self.bridge.state()["project"]["moduleDraft"], draft)
        self.assertFalse(self.workspace.project.get("module_reviewed"))

    def test_reviewed_sections_are_not_invalidated_by_reopening(self):
        values = {k: "Example" for k in ("summary", "theory", "tools", "tasks", "references", "discussion", "conclusion")}
        self.bridge.dispatch("saveSections", {"values": values, "reviewed": True})
        revision = self.workspace.project.get("revision")
        self.bridge.dispatch("saveSections", {"values": values, "reviewed": True})
        self.assertEqual(revision, self.workspace.project.get("revision"))

    def test_unknown_rpc_action_is_rejected(self):
        with self.assertRaises(ValueError):
            self.bridge.dispatch("readArbitraryFile", {"path": "C:/private.txt"})
