from threading import Event

from PySide6.QtCore import QObject, QRunnable, Signal


class Signals(QObject):
    done = Signal(object)
    failed = Signal(object)


class Worker(QRunnable):
    def __init__(self, function):
        super().__init__()
        self.function = function
        self.signals = Signals()
        self.cancel = Event()

    def run(self):
        try:
            result = self.function(self.cancel)
            self.signals.done.emit(result)
        except Exception as error:
            self.signals.failed.emit(error)
