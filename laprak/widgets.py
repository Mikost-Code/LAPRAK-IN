from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QSpinBox


class ScrollSafeSpinBox(QSpinBox):
    """Wheel events belong to the surrounding page, including while focused."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def wheelEvent(self, event):
        event.ignore()


class ScrollSafeComboBox(QComboBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def wheelEvent(self, event):
        event.ignore()
