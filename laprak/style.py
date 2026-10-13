from pathlib import Path

STYLE = """
QWidget { font-family: 'Segoe UI'; font-size: 13px; color: #191d24; }
QMainWindow, QDialog { background: #f7f8fa; }
QWidget#workflowPage { background: #f7f8fa; }
QWidget#documentEditor { background: white; }
QFrame#bar { background: #fcfcfd; border-bottom: 1px solid #dce0e4; }
QFrame#panel { background: #ffffff; border: 1px solid #dfe3e7; border-radius: 5px; }
QLabel#heading { font-size: 19px; font-weight: 650; }
QLabel#section { font-size: 14px; font-weight: 650; }
QLabel#muted { color: #656e7c; }
QLabel#success { color: #24683b; }
QLabel#badge { background: #fff5de; color: #7a5312; border: 1px solid #f2ddb1; padding: 5px 9px; border-radius: 5px; font-size: 11px; }
QLabel#warning { background: #fff5df; border: 1px solid #f4dfb1; padding: 10px; border-radius: 5px; color: #635126; }
QPushButton, QToolButton { background: #ffffff; border: 1px solid #cdd2d7; border-radius: 5px; padding: 9px 13px; }
QPushButton:hover, QToolButton:hover { background: #f0f4f0; border-color: #80a48a; }
QPushButton:pressed { background: #e6ede5; }
QPushButton#primary { background: #21633e; border: 1px solid #21633e; color: white; font-weight: 600; }
QPushButton#primary:hover { background: #194f31; }
QPushButton#primary:disabled { color: #89918f; background: #edf0ed; border-color: #dde2de; }
QPushButton#workflowNav { border: none; background: transparent; color: #656e7c; padding: 10px 16px; }
QPushButton#workflowNav:checked { background: #e4eee0; color: #173b20; font-weight: 600; }
QPushButton#workflowNav:disabled { color: #a3a9ad; background: transparent; }
QFrame#workflowCard, QWidget#workflowCard { background: white; border: 1px solid #dfe3e7; border-radius: 8px; }
QListWidget#recentReports { background: white; border: 1px solid #dfe3e7; border-radius: 8px; }
QPushButton#link { color: #24683b; background: transparent; border: none; padding: 4px; }
QPushButton:disabled { color: #89918f; background: #edf0ed; border-color: #dde2de; }
QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QComboBox, QDateEdit { background: white; border: 1px solid #d7dce1; border-radius: 5px; padding: 7px; selection-background-color: #dcebdd; selection-color: #172c1d; }
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QComboBox:focus { border: 1px solid #367449; }
QTextEdit, QPlainTextEdit { padding: 13px; line-height: 1.6; }
QListWidget { background: transparent; border: none; outline: none; }
QListWidget::item { padding: 14px 10px; border-radius: 5px; }
QListWidget::item:selected { background: #e4eee0; color: #173b20; }
QListWidget::item:hover { background: #f0f4ef; }
QTabWidget::pane { border: none; border-top: 1px solid #dfe3e7; background: white; }
QTabBar::tab { background: transparent; color: #606a78; padding: 13px 20px; border-bottom: 3px solid transparent; }
QTabBar::tab:selected { color: #191d24; border-bottom: 3px solid #347447; font-weight: 600; }
QCheckBox { spacing: 9px; padding: 5px 0; }
QCheckBox::indicator { width: 17px; height: 17px; }
QSplitter::handle { background: #f7f8fa; width: 7px; }
QScrollArea { border: none; background: white; }
QDialog#settingsDialog QWidget#settingsPage, QDialog#settingsDialog QWidget#settingsViewport { background: #ffffff; color: #191d24; }
QDialog#settingsDialog QLabel { background: transparent; }
QDialog#settingsDialog QLabel#section { padding-top: 5px; padding-bottom: 3px; color: #21633e; }
QDialog#settingsDialog QLabel#connectionStatus { background: #edf3ef; color: #254333; border: 1px solid #d4e3d9; border-radius: 5px; padding: 9px 12px; }
QDialog#settingsDialog QLineEdit, QDialog#settingsDialog QSpinBox, QDialog#settingsDialog QComboBox { min-height: 22px; }
QDialog#settingsDialog QComboBox { padding-right: 30px; }
QDialog#settingsDialog QComboBox::drop-down { subcontrol-origin: border; subcontrol-position: top right; width: 30px; border: none; }
QDialog#settingsDialog QComboBox::down-arrow { image: url(__ASSETS__/chevron-down.svg); width: 16px; height: 16px; }
QDialog#settingsDialog QSpinBox { padding-right: 30px; }
QDialog#settingsDialog QSpinBox::up-button { subcontrol-origin: border; subcontrol-position: top right; width: 28px; border: none; background: transparent; }
QDialog#settingsDialog QSpinBox::down-button { subcontrol-origin: border; subcontrol-position: bottom right; width: 28px; border: none; background: transparent; }
QDialog#settingsDialog QSpinBox::up-button:hover, QDialog#settingsDialog QSpinBox::down-button:hover { background: #edf3ee; }
QDialog#settingsDialog QSpinBox::up-arrow { image: url(__ASSETS__/chevron-up.svg); width: 12px; height: 12px; }
QDialog#settingsDialog QSpinBox::down-arrow { image: url(__ASSETS__/chevron-down.svg); width: 12px; height: 12px; }
QScrollBar:vertical { width: 8px; background: #f7f8fa; }
QScrollBar::handle:vertical { background: #c8cfcc; min-height: 25px; border-radius: 4px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QTableWidget { border: 1px solid #dfe3e7; background: white; gridline-color: #edf0f2; }
QHeaderView::section { background: #f7f8fa; border: none; padding: 8px; color: #5f6874; }
QStatusBar { border-top: 1px solid #dce0e4; background: #f8f9fa; }
QMenuBar, QMenu { background: white; }
QMenu::item { padding: 8px 24px; }
QMenu::item:selected { background: #e4eee0; }
""".replace("__ASSETS__", (Path(__file__).resolve().parent / "assets").as_posix())
