"""Qt worker threads for long-running scans and file operations."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QThread, Signal


class ScanWorker(QThread):
    progress = Signal(int, str)
    completed = Signal(object, int)
    failed = Signal(str)

    def __init__(self, scan_callable: Callable, save_callable: Callable, parent=None):
        super().__init__(parent)
        self.scan_callable = scan_callable
        self.save_callable = save_callable

    def run(self) -> None:
        try:
            result = self.scan_callable(
                progress_callback=lambda count, path: self.progress.emit(count, str(path))
            )
            scan_id = self.save_callable(result)
            self.completed.emit(result, scan_id)
        except Exception as error:
            self.failed.emit(str(error))


class ActionWorker(QThread):
    progress = Signal(int, int, str)
    completed = Signal(object)
    failed = Signal(str)

    def __init__(self, action: Callable, parent=None):
        super().__init__(parent)
        self.action = action

    def run(self) -> None:
        try:
            self.completed.emit(self.action())
        except Exception as error:
            self.failed.emit(str(error))


class ModelDownloadWorker(QThread):
    progress = Signal(int, int)
    completed = Signal(str)
    failed = Signal(str)

    def run(self) -> None:
        try:
            from .vision import download_image_model

            path = download_image_model(
                progress_callback=lambda done, total: self.progress.emit(done, total)
            )
            self.completed.emit(str(path))
        except Exception as error:
            self.failed.emit(str(error))
