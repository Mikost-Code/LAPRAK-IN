import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from threading import Event

import httpx
from PIL import Image
from pypdf import PdfWriter

from laprak.ai import AIError, Adapter, validate_endpoint
from laprak.pdf import extract_module
from laprak.report import escape, generate, copy_template
from laprak.storage import Project
from laprak.images import derivative, prepare_image


class CoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.project = Project.create(self.root / "session", {"title": "Ping & VLAN_10", "name": "Mahasiswa", "members": "A\nB"})
        self.step = self.project.steps()[0]["id"]
        self.image = self.root / "ping.png"
        Image.new("RGB", (100, 50), "white").save(self.image)

    def tearDown(self):
        self.project.close()
        self.temp.cleanup()

    def test_autosave_review_and_failed_test_final(self):
        self.project.import_image(self.image, self.step)
        self.project.set("module", {"path": "module/module.pdf"})
        self.project.set("module_reviewed", True)
        self.project.set("discussion", "Pengujian gagal.")
        self.project.set("conclusion", "Koneksi belum berhasil.")
        self.project.set("sections_reviewed", True)
        self.project.save_step(self.step, {"narrative": "Ping timeout", "result": "gagal"})
        self.project.save_step(self.step, {"reviewed": True, "checks": [True, True]}, invalidate=False)
        self.assertEqual(self.project.blockers(), [])
        self.project.save_step(self.step, {"notes": "Konfigurasi diperbaiki"})
        self.assertFalse(self.project.step(self.step)["reviewed"])
        self.assertFalse(any(self.project.step(self.step)["checks"]))

    def test_duplicates_corrupt_image_and_preserve_source(self):
        first = self.project.import_image(self.image, self.step)
        with self.assertRaises(FileExistsError):
            self.project.import_image(self.image, self.step)
        self.image.write_bytes(b"corrupt")
        with self.assertRaises(Exception):
            self.project.import_image(self.image, self.step)
        self.project.change_evidence(first, remove=True)
        self.assertEqual(self.project.evidence(), [])
        self.assertTrue(any((self.project.root / "screenshots/originals").iterdir()))

    def test_export_import_and_job_recovery(self):
        self.project.import_image(self.image, self.step)
        job_id = self.project.add_job("analyze_screenshot", self.step, {"prompt": "test"})
        self.project.job_status(job_id, "running")
        output = self.root / "portable.zip"
        self.project.export_zip(output)
        copy = Project.import_zip(output, self.root / "restored")
        try:
            self.assertEqual(copy.step(self.step)["title"], "Langkah pertama")
            self.assertEqual(copy.jobs()[0]["status"], "interrupted")
            self.assertTrue((copy.root / copy.evidence()[0]["path"]).exists())
        finally:
            copy.close()

    def test_zip_traversal_rejected_before_extraction(self):
        source = self.root / "unsafe.zip"
        with zipfile.ZipFile(source, "w") as archive:
            archive.writestr("manifest.json", json.dumps({"schema_version": 1, "format": "laprak-project"}))
            archive.writestr("../escape.txt", "outside")
            archive.writestr("session.sqlite", "placeholder")
        with self.assertRaises(ValueError):
            Project.import_zip(source, self.root / "unsafe")
        self.assertFalse((self.root / "escape.txt").exists())

    def test_template_original_untouched_and_escape(self):
        source = Path(__file__).resolve().parents[1] / "template"
        original = (source / "main.tex").read_bytes()
        copy_template(source, self.project.root / "template")
        self.project.import_image(self.image, self.step)
        self.project.save_step(self.step, {"narrative": "IP_1 & 50% # $ { } ~ ^ \\"})
        workspace, main, manifest = generate(self.project.root, self.project.snapshot())
        self.assertEqual((source / "main.tex").read_bytes(), original)
        text = (workspace / "generated/documentation.tex").read_text(encoding="utf-8")
        self.assertIn(r"IP\_1 \& 50\%", text)
        self.assertIn("keepaspectratio", text)
        self.assertIn("../generated/identity", main.read_text(encoding="utf-8"))
        self.assertEqual(escape("\\%"), r"\textbackslash{}\%")

    def test_scanned_pdf_not_claimed_read(self):
        source = self.root / "scan.pdf"
        writer = PdfWriter()
        writer.add_blank_page(width=100, height=100)
        writer.write(source)
        result = extract_module(source)
        self.assertTrue(result[0]["needs_vision"])
        self.assertEqual(result[0]["page"], 1)

    def test_derivatives_preserve_original_and_invalidate_review(self):
        prepared = prepare_image(self.project.root, self.image, Event())
        self.project.register_image(prepared, self.step)
        self.project.save_step(self.step, {"reviewed": True}, invalidate=False)
        path = derivative(self.project.root, prepared["path"], rect=(0, 0, 50, 25))
        self.project.set_derivative(prepared["id"], path)
        self.assertFalse(self.project.step(self.step)["reviewed"])
        with Image.open(self.project.root / prepared["path"]) as original:
            self.assertEqual(original.size, (100, 50))
        with Image.open(self.project.root / path) as cropped:
            self.assertEqual(cropped.size, (50, 25))
        with self.assertRaises(ValueError):
            derivative(self.project.root, prepared["path"], rect=(0, 0, 101, 25))


class ProviderTests(unittest.TestCase):
    def config(self):
        return {"provider": "API kompatibel OpenAI", "endpoint": "https://example.test/v1", "model": "test", "structured": "JSON", "vision": True}

    def test_wire_format_and_ai_facts_always_unreviewed(self):
        def handler(request):
            payload = json.loads(request.content)
            self.assertEqual(payload["response_format"], {"type": "json_object"})
            self.assertEqual(payload["model"], "test")
            result = {"facts": [{"type": "ping", "value": "timeout", "source": "image-1", "reviewed": True}], "narrative": "Ping gagal.", "unknown": [], "result": "gagal"}
            return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(result)}}]})
        result = Adapter(self.config(), "test-secret", httpx.MockTransport(handler)).run("test")
        self.assertFalse(result["facts"][0]["reviewed"])
        self.assertEqual(result["result"], "gagal")

    def test_auth_no_retry_and_no_secret_in_error(self):
        adapter = Adapter(self.config(), "secret-token", httpx.MockTransport(lambda request: httpx.Response(401, json={"error": "secret-token"})))
        with self.assertRaises(AIError) as caught:
            adapter.run("test")
        self.assertTrue(caught.exception.auth)
        self.assertFalse(caught.exception.retryable)
        self.assertNotIn("secret-token", str(caught.exception))

    def test_retry_after_and_cancellation(self):
        adapter = Adapter(self.config(), transport=httpx.MockTransport(lambda request: httpx.Response(429, headers={"Retry-After": "30"})))
        with self.assertRaises(AIError) as caught:
            adapter.run("test")
        self.assertEqual(caught.exception.delay, 30)
        cancel = Event()
        cancel.set()
        with self.assertRaises(AIError):
            adapter.run("test", cancel=cancel)

    def test_endpoint_credentials_rejected(self):
        for endpoint in ("https://secret@example.test", "https://example.test?key=secret", "http://remote.test"):
            with self.assertRaises(ValueError):
                validate_endpoint(endpoint)
        self.assertEqual(validate_endpoint("http://localhost:11434/"), "http://localhost:11434")


if __name__ == "__main__":
    unittest.main()
