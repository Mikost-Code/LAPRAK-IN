import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from laprak.ai import Credentials
from laprak.app import configure_app
from laprak.dialogs import SettingsDialog


class SettingsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        dark = cls.app.palette()
        dark.setColor(QPalette.ColorRole.Window, QColor("#202020"))
        dark.setColor(QPalette.ColorRole.Base, QColor("#202020"))
        cls.app.setPalette(dark)
        configure_app(cls.app)

    def setUp(self):
        self.dialog = SettingsDialog(None, {"provider": "API kompatibel OpenAI", "endpoint": "https://api.openai.com/v1",
                                           "model": "test-model"}, Credentials(), lambda *args: None)
        self.dialog.resize(640, 480)
        self.dialog.tabs.setCurrentIndex(2)
        self.dialog.show()
        self.app.processEvents()

    def tearDown(self):
        self.dialog.close()
        self.app.processEvents()

    def test_codex_hides_technical_credentials_and_sets_default_model(self):
        self.dialog.tabs.setCurrentIndex(1)
        self.dialog.secret.setText("old-provider-secret")
        self.dialog.provider.setCurrentText("GPT (login Codex)")
        self.app.processEvents()
        self.assertTrue(self.dialog.endpoint.isHidden())
        self.assertTrue(self.dialog.secret.isHidden())
        self.assertEqual(self.dialog.secret.text(), "")
        self.assertTrue(self.dialog.connect_button.isVisible())
        self.dialog.login_done("account-default")
        self.assertEqual(self.dialog.values()["model"], "account-default")
        self.assertEqual(self.dialog.values()["endpoint"], "codex://local")
        self.assertIn("Kembali ke Laprak", self.dialog.test_status.text())

    def wheel_over(self, widget, delta):
        self.dialog.advanced_scroll.ensureWidgetVisible(widget)
        widget.setFocus()
        self.app.processEvents()
        point = widget.mapTo(self.dialog, widget.rect().center())
        QTest.wheelEvent(self.dialog.windowHandle(), point, QPoint(0, delta))
        self.app.processEvents()

    def test_focused_numbers_never_change_on_wheel_and_page_scrolls(self):
        controls = (self.dialog.timeout, self.dialog.image_size, self.dialog.max_jobs,
                    self.dialog.pdf_mb, self.dialog.pdf_pages)
        for control in controls:
            self.dialog.advanced_scroll.ensureWidgetVisible(control)
            self.app.processEvents()
            bar = self.dialog.advanced_scroll.verticalScrollBar()
            before_scroll = bar.value()
            before = control.value()
            delta = -120 if before_scroll < bar.maximum() else 120
            self.wheel_over(control, delta)
            self.assertEqual(control.value(), before)
            self.assertNotEqual(bar.value(), before_scroll, "Wheel must reach the scroll area")

    def test_combo_wheel_does_not_change_selection(self):
        self.dialog.structured.setCurrentIndex(1)
        self.wheel_over(self.dialog.structured, -120)
        self.assertEqual(self.dialog.structured.currentIndex(), 1)

    def test_keyboard_editing_and_values_still_work(self):
        self.dialog.timeout.setFocus()
        before = self.dialog.timeout.value()
        QTest.keyClick(self.dialog.timeout, Qt.Key.Key_Up)
        self.assertEqual(self.dialog.timeout.value(), before + 1)
        self.assertEqual(self.dialog.values()["timeout"], before + 1)
        self.assertGreater(self.dialog.timeout.lineEdit().width(), 100)

    def test_light_controls_after_dark_system_palette(self):
        self.assertGreater(self.dialog.timeout.lineEdit().palette().color(QPalette.ColorRole.Base).lightness(), 200)
        self.assertLess(self.dialog.timeout.lineEdit().palette().color(QPalette.ColorRole.Text).lightness(), 80)
        self.dialog.tabs.setCurrentIndex(1)
        self.app.processEvents()
        self.assertGreater(self.dialog.ai_scroll.widget().palette().color(QPalette.ColorRole.Window).lightness(), 200)

    def test_selecting_zen_api_sets_endpoint_and_prompt_json(self):
        self.dialog.tabs.setCurrentIndex(1)
        self.dialog.secret.setText("old-secret")
        self.dialog.provider.setCurrentText("OpenCode Zen (API)")
        self.app.processEvents()
        self.assertEqual(self.dialog.endpoint.text(), "https://opencode.ai/zen/v1")
        self.assertEqual(self.dialog.secret.text(), "")
        self.assertEqual(self.dialog.structured.currentText(), "Prompt JSON")
        self.assertTrue(self.dialog.provider_hint.isVisible())

    def test_saved_wrong_zen_configuration_is_repaired_on_open(self):
        dialog = SettingsDialog(None, {"provider": "OpenCode", "endpoint": "https://opencode.ai/zen/v1",
                                       "model": "free"}, Credentials(), lambda *args: None)
        self.assertEqual(dialog.provider.currentText(), "OpenCode Zen (API)")
        self.assertEqual(dialog.model.text(), "")
        self.assertIn("Zen terdeteksi", dialog.test_status.text())
        dialog.close()


if __name__ == "__main__":
    unittest.main()
