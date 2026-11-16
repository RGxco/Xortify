"""Main desktop interface for reviewing and applying file organization."""

from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import QPoint, QPointF, QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QCloseEvent,
    QFont,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QRadialGradient,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QFileDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QHeaderView,
)

from .database import XortifyDatabase
from .intelligence import LocalPlacementAssistant, topic_from_destination
from .models import OperationResult, PlanItem, ScanResult, UndoResult
from .operations import execute_selected, undo_operation
from .planner import build_plan
from .scanner import scan_directory
from .vision import analyze_image_files, image_model_installed, vision_runtime_available
from .workers import ActionWorker, ModelDownloadWorker, ScanWorker


def _database_path() -> Path:
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return base / "Xortify" / "xortify.sqlite3"


def _format_size(size: int) -> str:
    units = ("B", "KB", "MB", "GB", "TB")
    value = float(size)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            return f"{value:.0f} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    return f"{size} B"


def _table(headers: list[str]) -> QTableWidget:
    table = QTableWidget(0, len(headers))
    table.setHorizontalHeaderLabels(headers)
    table.setAlternatingRowColors(True)
    table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    table.verticalHeader().setVisible(False)
    table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
    table.horizontalHeader().setStretchLastSection(True)
    return table


class AeroCanvas(QWidget):
    """Soft sky, water, and glass accents for the Frutiger Aero interface."""

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt override name
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        width, height = self.width(), self.height()

        sky = QLinearGradient(0, 0, 0, height)
        sky.setColorAt(0.0, QColor("#65c9ef"))
        sky.setColorAt(0.36, QColor("#a8e8f6"))
        sky.setColorAt(0.73, QColor("#e1f7fb"))
        sky.setColorAt(1.0, QColor("#eaf9f8"))
        painter.fillRect(self.rect(), sky)

        # Diffuse sunlight in the upper-right corner.
        sun = QRadialGradient(QPointF(width * 0.87, height * 0.13), max(140, width * 0.28))
        sun.setColorAt(0.0, QColor(255, 255, 255, 100))
        sun.setColorAt(0.48, QColor(255, 255, 255, 38))
        sun.setColorAt(1.0, QColor(255, 255, 255, 0))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(sun)
        painter.drawEllipse(QRectF(width * 0.56, -height * 0.16, width * 0.62, height * 0.58))

        # Loose cloud puffs give the background a quiet, airy texture.
        painter.setBrush(QColor(255, 255, 255, 35))
        for x, y, radius in (
            (width * 0.06, height * 0.16, 35),
            (width * 0.10, height * 0.14, 48),
            (width * 0.15, height * 0.16, 32),
            (width * 0.75, height * 0.28, 24),
            (width * 0.79, height * 0.26, 34),
            (width * 0.83, height * 0.29, 22),
        ):
            painter.drawEllipse(QPointF(x, y), radius, radius * 0.55)

        # Translucent bubbles sit behind the content like reflected light.
        for x, y, radius in (
            (width * 0.035, height * 0.65, 19),
            (width * 0.955, height * 0.48, 25),
            (width * 0.91, height * 0.72, 11),
            (width * 0.12, height * 0.87, 10),
        ):
            bubble = QRadialGradient(QPointF(x - radius * 0.28, y - radius * 0.32), radius * 1.55)
            bubble.setColorAt(0.0, QColor(255, 255, 255, 165))
            bubble.setColorAt(0.34, QColor(232, 255, 255, 92))
            bubble.setColorAt(1.0, QColor(55, 191, 219, 17))
            painter.setBrush(bubble)
            painter.setPen(QColor(255, 255, 255, 92))
            painter.drawEllipse(QPointF(x, y), radius, radius)

        # A pair of low rolling waves adds the sea-and-meadow color signature.
        water = QPainterPath()
        water.moveTo(0, height * 0.91)
        water.cubicTo(width * 0.23, height * 0.80, width * 0.42, height * 0.94, width * 0.62, height * 0.87)
        water.cubicTo(width * 0.79, height * 0.81, width * 0.89, height * 0.90, width, height * 0.82)
        water.lineTo(width, height)
        water.lineTo(0, height)
        water.closeSubpath()
        water_gradient = QLinearGradient(0, height * 0.82, 0, height)
        water_gradient.setColorAt(0, QColor(90, 211, 226, 75))
        water_gradient.setColorAt(1, QColor(36, 166, 205, 105))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(water_gradient)
        painter.drawPath(water)

        meadow = QPainterPath()
        meadow.moveTo(0, height * 0.96)
        meadow.cubicTo(width * 0.20, height * 0.88, width * 0.36, height * 1.01, width * 0.55, height * 0.94)
        meadow.cubicTo(width * 0.73, height * 0.87, width * 0.87, height * 0.97, width, height * 0.91)
        meadow.lineTo(width, height)
        meadow.lineTo(0, height)
        meadow.closeSubpath()
        meadow_gradient = QLinearGradient(0, height * 0.90, 0, height)
        meadow_gradient.setColorAt(0, QColor(125, 216, 164, 72))
        meadow_gradient.setColorAt(1, QColor(77, 184, 143, 92))
        painter.setBrush(meadow_gradient)
        painter.drawPath(meadow)


class AeroSwitch(QCheckBox):
    """Compact glossy switch for approving an individual proposed move."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(42, 28)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def hitButton(self, position: QPoint) -> bool:  # noqa: N802 - Qt override name
        return self.rect().contains(position)

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt override name
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        track = QRectF(4, (self.height() - 17) / 2, 34, 17)
        checked = self.isChecked()
        track_gradient = QLinearGradient(track.topLeft(), track.bottomLeft())
        if checked:
            track_gradient.setColorAt(0, QColor("#52daca"))
            track_gradient.setColorAt(1, QColor("#159bb0"))
            border = QColor("#138b9d")
        else:
            track_gradient.setColorAt(0, QColor("#f5feff"))
            track_gradient.setColorAt(1, QColor("#d5edf2"))
            border = QColor("#91c5d2")
        painter.setPen(border)
        painter.setBrush(track_gradient)
        painter.drawRoundedRect(track, 8.5, 8.5)

        knob_size = 13
        knob_center_x = track.right() - 8.5 if checked else track.left() + 8.5
        knob = QRectF(knob_center_x - knob_size / 2, track.center().y() - knob_size / 2, knob_size, knob_size)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(14, 88, 112, 40))
        painter.drawEllipse(knob.translated(0, 1))
        knob_gradient = QLinearGradient(knob.topLeft(), knob.bottomLeft())
        knob_gradient.setColorAt(0, QColor("#ffffff"))
        knob_gradient.setColorAt(1, QColor("#d8f5f6"))
        painter.setPen(QColor("#f7ffff"))
        painter.setBrush(knob_gradient)
        painter.drawEllipse(knob)
        if self.hasFocus():
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QColor(30, 132, 170, 150))
            painter.drawRoundedRect(track.adjusted(-2, -2, 2, 2), 10, 10)


class MetricCard(QFrame):
    def __init__(self, title: str, value: str = "—", hint: str = "", parent=None):
        super().__init__(parent)
        self.setObjectName("metricCard")
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(22)
        shadow.setOffset(0, 5)
        shadow.setColor(QColor(26, 105, 139, 35))
        self.setGraphicsEffect(shadow)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        title_label = QLabel(title.upper())
        title_label.setObjectName("metricTitle")
        self.value_label = QLabel(value)
        self.value_label.setObjectName("metricValue")
        self.hint_label = QLabel(hint)
        self.hint_label.setObjectName("metricHint")
        layout.addWidget(title_label)
        layout.addWidget(self.value_label)
        layout.addWidget(self.hint_label)

    def set_value(self, value: str, hint: str = "") -> None:
        self.value_label.setText(value)
        self.hint_label.setText(hint)


class MainWindow(QMainWindow):
    def __init__(self, database: XortifyDatabase | None = None):
        super().__init__()
        self.database = database or XortifyDatabase(_database_path())
        self.scan_result: ScanResult | None = None
        self.plan: list[PlanItem] = []
        self.active_worker: ScanWorker | ActionWorker | ModelDownloadWorker | None = None
        self.setWindowTitle("Xortify — Local File Intelligence")
        self.resize(1180, 780)
        self.setMinimumSize(920, 620)
        self._build_ui()
        self._refresh_model_status()
        self._refresh_history()

    def closeEvent(self, event: QCloseEvent) -> None:
        if self.active_worker is not None and self.active_worker.isRunning():
            QMessageBox.information(
                self,
                "Work is still in progress",
                "Wait for the current scan or file operation to finish before closing Xortify.",
            )
            event.ignore()
            return
        event.accept()

    def _build_ui(self) -> None:
        central = AeroCanvas()
        central.setObjectName("aeroCanvas")
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(28, 22, 28, 22)
        root_layout.setSpacing(16)

        header = QHBoxLayout()
        title_stack = QVBoxLayout()
        title = QLabel("Xortify")
        title.setObjectName("appTitle")
        subtitle = QLabel("Fresh folders. Clear skies. Your files stay local.")
        subtitle.setObjectName("subtitle")
        title_stack.addWidget(title)
        title_stack.addWidget(subtitle)
        header.addLayout(title_stack)
        header.addStretch(1)
        privacy = QLabel("●  FILES STAY LOCAL")
        privacy.setObjectName("privacyBadge")
        header.addWidget(privacy, alignment=Qt.AlignmentFlag.AlignTop)
        root_layout.addLayout(header)

        folder_card = QFrame()
        folder_card.setObjectName("folderCard")
        folder_shadow = QGraphicsDropShadowEffect(folder_card)
        folder_shadow.setBlurRadius(22)
        folder_shadow.setOffset(0, 5)
        folder_shadow.setColor(QColor(26, 105, 139, 33))
        folder_card.setGraphicsEffect(folder_shadow)
        folder_layout = QVBoxLayout(folder_card)
        folder_layout.setContentsMargins(18, 14, 18, 16)
        folder_label = QLabel("Choose a folder to explore")
        folder_label.setObjectName("sectionTitle")
        folder_row = QHBoxLayout()
        self.folder_input = QLineEdit()
        self.folder_input.setPlaceholderText("Choose a folder to preview its organization")
        self.folder_input.setClearButtonEnabled(True)
        self.browse_button = QPushButton("Browse…")
        self.browse_button.clicked.connect(self._browse)
        self.scan_button = QPushButton("Scan folder")
        self.scan_button.setObjectName("primaryButton")
        self.scan_button.clicked.connect(self._start_scan)
        folder_row.addWidget(self.folder_input, 1)
        folder_row.addWidget(self.browse_button)
        folder_row.addWidget(self.scan_button)
        folder_layout.addWidget(folder_label)
        folder_layout.addLayout(folder_row)
        model_row = QHBoxLayout()
        self.model_status_label = QLabel()
        self.model_status_label.setObjectName("aiHint")
        self.install_ai_button = QPushButton("Download image AI · 5 MB")
        self.install_ai_button.clicked.connect(self._install_image_ai)
        model_row.addWidget(self.model_status_label, 1)
        model_row.addWidget(self.install_ai_button)
        folder_layout.addLayout(model_row)
        root_layout.addWidget(folder_card)

        metrics = QGridLayout()
        metrics.setSpacing(12)
        self.files_card = MetricCard("Files scanned", "—", "No scan yet")
        self.duplicates_card = MetricCard("Exact duplicate files", "—", "SHA-256")
        self.large_card = MetricCard("Large files", "—", "500 MiB or larger")
        self.empty_card = MetricCard("Empty folders", "—", "No automatic deletion")
        for column, card in enumerate((self.files_card, self.duplicates_card, self.large_card, self.empty_card)):
            metrics.addWidget(card, 0, column)
        root_layout.addLayout(metrics)

        self.progress = QProgressBar()
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        self.status_label = QLabel("Ready for a fresh scan. Your files remain untouched until you approve a move.")
        self.status_label.setObjectName("statusLabel")

        self.tabs = QTabWidget()
        self.plan_tab = QWidget()
        plan_layout = QVBoxLayout(self.plan_tab)
        plan_layout.setContentsMargins(10, 14, 10, 12)
        plan_toolbar = QHBoxLayout()
        plan_heading = QLabel("Proposed organization")
        plan_heading.setObjectName("sectionTitle")
        self.plan_count_label = QLabel("Scan a folder to prepare a preview.")
        self.select_all_button = QPushButton("Select all")
        self.select_none_button = QPushButton("Select none")
        self.select_all_button.clicked.connect(lambda: self._set_all_plan_checks(True))
        self.select_none_button.clicked.connect(lambda: self._set_all_plan_checks(False))
        plan_toolbar.addWidget(plan_heading)
        plan_toolbar.addSpacing(12)
        plan_toolbar.addWidget(self.plan_count_label)
        plan_toolbar.addStretch(1)
        plan_toolbar.addWidget(self.select_all_button)
        plan_toolbar.addWidget(self.select_none_button)
        plan_layout.addLayout(plan_toolbar)
        self.ai_hint_label = QLabel(
            "Install the optional image model to group recognizable pictures across folders. Code projects stay intact. Double-click a proposed path to review or change it."
        )
        self.ai_hint_label.setObjectName("aiHint")
        plan_layout.addWidget(self.ai_hint_label)

        self.plan_table = _table(["Use", "Category", "Current location", "Proposed location", "Size", "Local AI & findings"])
        self.plan_table.setColumnWidth(0, 56)
        self.plan_table.setColumnWidth(1, 110)
        self.plan_table.setColumnWidth(4, 86)
        self.plan_table.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked | QAbstractItemView.EditTrigger.EditKeyPressed
        )
        self.plan_table.itemChanged.connect(self._handle_plan_edit)
        plan_layout.addWidget(self.plan_table, 1)

        plan_bottom = QHBoxLayout()
        self.preview_note = QLabel("Preview only — no files have been changed.")
        self.preview_note.setObjectName("previewNote")
        self.undo_button = QPushButton("Undo latest move")
        self.undo_button.setEnabled(self.database.latest_undoable_operation() is not None)
        self.undo_button.clicked.connect(self._start_undo)
        self.move_button = QPushButton("Move selected items")
        self.move_button.setObjectName("primaryButton")
        self.move_button.setEnabled(False)
        self.move_button.clicked.connect(self._confirm_execute)
        plan_bottom.addWidget(self.preview_note, 1)
        plan_bottom.addWidget(self.undo_button)
        plan_bottom.addWidget(self.move_button)
        plan_layout.addLayout(plan_bottom)
        self.tabs.addTab(self.plan_tab, "Review plan")

        self.findings_tab = QTabWidget()
        self.duplicates_table = _table(["Group", "Size", "File location", "SHA-256"])
        self.large_table = _table(["Size", "Category", "File location"])
        self.empty_table = _table(["Empty folder"])
        self.unreadable_table = _table(["File or folder", "Reason"])
        for table, title_text in (
            (self.duplicates_table, "Exact duplicates"),
            (self.large_table, "Large files"),
            (self.empty_table, "Empty folders"),
            (self.unreadable_table, "Could not read"),
        ):
            self.findings_tab.addTab(table, title_text)
        self.tabs.addTab(self.findings_tab, "Findings")

        self.history_table = _table(["When", "Folder", "Action", "Status"])
        self.tabs.addTab(self.history_table, "Activity")
        root_layout.addWidget(self.tabs, 1)
        root_layout.addWidget(self.progress)
        root_layout.addWidget(self.status_label)
        self.setCentralWidget(central)
        self._apply_style()

    def _apply_style(self) -> None:
        self.setFont(QFont("Segoe UI", 10))
        self.setStyleSheet(
            """
            QMainWindow { background: #8edff2; color: #14445d; }
            QWidget { color: #164861; }
            QWidget#aeroCanvas { background: transparent; color: #164861; }
            QLabel#appTitle { font-size: 31px; font-weight: 750; color: #075d80; }
            QLabel#subtitle { color: #286d85; font-size: 12px; }
            QLabel#privacyBadge { background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #f8fff5, stop:0.48 #d7f8d8, stop:1 #a9e5b7); color: #247244; border: 1px solid rgba(255,255,255,220); border-bottom-color: #83cda0; border-radius: 12px; padding: 7px 11px; font-size: 10px; font-weight: 750; }
            QFrame#folderCard, QFrame#metricCard { background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 rgba(255,255,255,240), stop:0.12 rgba(255,255,255,222), stop:1 rgba(225,250,255,218)); border: 1px solid rgba(255,255,255,245); border-bottom: 1px solid rgba(64,166,197,105); border-radius: 16px; }
            QLabel#sectionTitle { font-weight: 750; color: #125c77; font-size: 13px; }
            QLabel#metricTitle { color: #398099; font-size: 9px; font-weight: 750; letter-spacing: 1px; }
            QLabel#metricValue { color: #0b6386; font-size: 26px; font-weight: 750; }
            QLabel#metricHint, QLabel#statusLabel { color: #39778b; font-size: 10px; }
            QLabel#previewNote { color: #21814e; font-weight: 700; }
            QLabel#aiHint { color: #39778b; font-size: 10px; padding: 1px 2px 4px 2px; }
            QLineEdit { background: rgba(255,255,255,238); border: 1px solid #a9dce9; border-bottom-color: #82c4d7; border-radius: 9px; padding: 10px 12px; color: #174a61; selection-background-color: #7ed8ec; }
            QLineEdit:focus { border: 1px solid #48b6d3; background: rgba(255,255,255,252); }
            QPushButton { background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #ffffff, stop:0.45 #e7faff, stop:1 #ccecf5); border: 1px solid #a7d9e8; border-bottom: 2px solid #83bfd2; border-radius: 10px; padding: 9px 14px; color: #17617d; font-weight: 700; }
            QPushButton:hover { background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #ffffff, stop:0.4 #f2ffff, stop:1 #b9edf5); border-color: #6bc3da; }
            QPushButton:pressed { background: #bce6ef; border-bottom-width: 1px; padding-top: 10px; }
            QPushButton:disabled { color: #83aab6; background: #e4f0f2; border-color: #cfdee2; }
            QPushButton#primaryButton { background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #67e4d5, stop:0.16 #39cfc8, stop:0.55 #159ec1, stop:1 #117ba9); border: 1px solid #8af1e2; border-bottom: 2px solid #0e7299; color: white; }
            QPushButton#primaryButton:hover { background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #85f2e1, stop:0.22 #4bded4, stop:0.58 #21afd0, stop:1 #128ab7); }
            QPushButton#primaryButton:pressed { background: #1183aa; }
            QTabWidget::pane { background: rgba(247,254,255,236); border: 1px solid rgba(255,255,255,240); border-bottom-color: #91d0dd; border-radius: 14px; top: -1px; }
            QTabBar::tab { background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 rgba(255,255,255,190), stop:1 rgba(211,241,248,210)); color: #3c7b91; padding: 9px 18px; margin-right: 5px; border: 1px solid rgba(255,255,255,180); border-bottom-color: #9aceda; border-top-left-radius: 10px; border-top-right-radius: 10px; }
            QTabBar::tab:selected { background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #ffffff, stop:1 #e9fbff); color: #087b9c; font-weight: 750; border-bottom-color: white; }
            QTableWidget { background: rgba(255,255,255,220); alternate-background-color: rgba(222,247,251,145); border: 0; color: #164861; gridline-color: rgba(86,167,191,70); selection-background-color: #b9edf1; selection-color: #124f69; }
            QTableWidget::item { color: #164861; padding: 2px 4px; }
            QHeaderView::section { background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #edfcff, stop:1 #d3f0f7); color: #33758b; border: 0; border-bottom: 1px solid #b1dfe9; padding: 9px; font-weight: 750; }
            QProgressBar { border: 1px solid rgba(255,255,255,220); border-radius: 5px; background: rgba(193,233,240,190); height: 8px; }
            QProgressBar::chunk { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #48d4bc, stop:0.55 #36c4d5, stop:1 #248ed0); border-radius: 4px; }
            """
        )

    def _browse(self) -> None:
        start = self.folder_input.text().strip() or str(Path.home())
        selected = QFileDialog.getExistingDirectory(self, "Choose a folder", start)
        if selected:
            self.folder_input.setText(selected)

    def _selected_root(self) -> Path | None:
        entered = self.folder_input.text().strip().strip('"')
        path = Path(entered).expanduser() if entered else None
        if path is None or not path.exists() or not path.is_dir():
            QMessageBox.warning(self, "Choose a folder", "Enter or browse to an existing folder first.")
            return None
        return path.resolve()

    def _set_busy(self, busy: bool, message: str = "") -> None:
        self.scan_button.setEnabled(not busy)
        self.browse_button.setEnabled(not busy)
        self.folder_input.setEnabled(not busy)
        self.install_ai_button.setEnabled(
            not busy and vision_runtime_available() and not image_model_installed()
        )
        self.move_button.setEnabled(False if busy else self.move_button.isEnabled())
        self.undo_button.setEnabled(False if busy else self.database.latest_undoable_operation() is not None)
        self.progress.setRange(0, 0 if busy else 1)
        if not busy:
            self.progress.setValue(0)
        if message:
            self.status_label.setText(message)

    def _refresh_model_status(self) -> None:
        installed = image_model_installed()
        runtime_available = vision_runtime_available()
        if not runtime_available:
            self.model_status_label.setText(
                "Photo AI needs the optional vision setup. See the Windows setup steps."
            )
            self.install_ai_button.setText("Image AI unavailable")
            self.install_ai_button.setEnabled(False)
            self.ai_hint_label.setText(
                "Basic scanning still works. Install the optional vision setup before using local photo analysis."
            )
        elif installed:
            self.model_status_label.setText(
                "Image AI ready · pictures are analyzed on this PC; no photo upload."
            )
            self.install_ai_button.setText("Image AI installed")
            self.ai_hint_label.setText(
                "The local image model groups familiar subjects such as cats, dogs, birds, food, vehicles, and nature. "
                "Unclear photos keep the normal review suggestion; code projects stay intact."
            )
        else:
            self.model_status_label.setText(
                "Optional 5 MB image model · downloads once, then works offline."
            )
            self.install_ai_button.setText("Download image AI · 5 MB")
            self.ai_hint_label.setText(
                "Image AI is optional: download it once to group familiar photos across source folders. "
                "Pictures stay on this PC; code projects stay together."
            )
            self.install_ai_button.setEnabled(not installed)

    def _install_image_ai(self) -> None:
        if not vision_runtime_available():
            QMessageBox.information(
                self,
                "Set up image AI first",
                "Install Xortify with the optional vision dependencies before downloading the model.",
            )
            return
        if image_model_installed():
            self._refresh_model_status()
            return
        self._set_busy(True, "Downloading the small local image model…")
        self.active_worker = ModelDownloadWorker(self)
        self.active_worker.progress.connect(self._model_download_progress)
        self.active_worker.completed.connect(self._model_download_completed)
        self.active_worker.failed.connect(self._model_download_failed)
        self.active_worker.start()

    def _model_download_progress(self, done: int, total: int) -> None:
        percent = int(done * 100 / total) if total else 0
        self.status_label.setText(f"Downloading local image model · {percent}%")

    def _model_download_completed(self, path_text: str) -> None:
        self._set_busy(False)
        self._refresh_model_status()
        self.status_label.setText("Image AI installed. The next scan can group recognizable photos.")

    def _model_download_failed(self, message: str) -> None:
        self._set_busy(False)
        self._refresh_model_status()
        self.status_label.setText("Image model could not be installed.")
        QMessageBox.critical(self, "Image AI download failed", message)

    def _start_scan(self) -> None:
        root = self._selected_root()
        if root is None:
            return
        self._set_busy(True, "Starting read-only scan…")
        self.scan_button.setText("Scanning…")

        def scan(progress_callback):
            result = scan_directory(root, progress_callback=progress_callback)
            if vision_runtime_available() and image_model_installed():
                analyze_image_files(
                    result.files,
                    result.project_directories,
                    progress_callback=lambda done, total, path: progress_callback(
                        done, f"AI: {done:,}/{total:,} · {path}"
                    ),
                )
            return result

        self.active_worker = ScanWorker(scan, self.database.record_scan, self)
        self.active_worker.progress.connect(self._scan_progress)
        self.active_worker.completed.connect(self._scan_completed)
        self.active_worker.failed.connect(self._worker_failed)
        self.active_worker.finished.connect(lambda: self.scan_button.setText("Scan folder"))
        self.active_worker.start()

    def _scan_progress(self, count: int, path_text: str) -> None:
        if path_text.startswith("AI: "):
            self.status_label.setText(f"Local image AI · {path_text[4:]}")
        else:
            self.status_label.setText(f"Scanned {count:,} files · {path_text}")

    def _scan_completed(self, result: ScanResult, scan_id: int) -> None:
        self._set_busy(False)
        self.scan_result = result
        assistant = LocalPlacementAssistant(self.database.recent_placement_examples())
        self.plan = build_plan(result, assistant)
        self.files_card.set_value(f"{len(result.files):,}", f"Scan #{scan_id}")
        self.duplicates_card.set_value(f"{result.duplicate_file_count:,}", f"{len(result.duplicate_groups):,} matching groups")
        self.large_card.set_value(f"{len(result.large_files):,}", "500 MiB or larger")
        self.empty_card.set_value(f"{len(result.empty_directories):,}", "No automatic deletion")
        self._populate_findings(result)
        self._populate_plan()
        self._refresh_history()
        self.status_label.setText(
            f"Scan complete: {len(result.files):,} files checked in {result.root}."
            + (f" {len(result.project_directories)} complete project folder(s) protected." if result.project_directories else "")
            + (f" {len(result.unreadable_files)} item(s) could not be read." if result.unreadable_files else "")
        )
        self.tabs.setCurrentWidget(self.plan_tab)

    def _populate_findings(self, result: ScanResult) -> None:
        self.duplicates_table.setRowCount(0)
        duplicate_group_id = 1
        for group in result.duplicate_groups:
            for record in group:
                row = self.duplicates_table.rowCount()
                self.duplicates_table.insertRow(row)
                values = (str(duplicate_group_id), _format_size(record.size), str(record.path), record.sha256)
                for col, value in enumerate(values):
                    item = QTableWidgetItem(value)
                    item.setToolTip(value)
                    self.duplicates_table.setItem(row, col, item)
            duplicate_group_id += 1

        self.large_table.setRowCount(0)
        for record in result.large_files:
            row = self.large_table.rowCount()
            self.large_table.insertRow(row)
            for col, value in enumerate((_format_size(record.size), record.category, str(record.path))):
                item = QTableWidgetItem(value)
                item.setToolTip(value)
                self.large_table.setItem(row, col, item)

        self.empty_table.setRowCount(0)
        for path in result.empty_directories:
            row = self.empty_table.rowCount()
            self.empty_table.insertRow(row)
            self.empty_table.setItem(row, 0, QTableWidgetItem(str(path)))

        self.unreadable_table.setRowCount(0)
        for path, reason in result.unreadable_files:
            row = self.unreadable_table.rowCount()
            self.unreadable_table.insertRow(row)
            self.unreadable_table.setItem(row, 0, QTableWidgetItem(str(path)))
            self.unreadable_table.setItem(row, 1, QTableWidgetItem(reason))

    def _populate_plan(self) -> None:
        self.plan_table.blockSignals(True)
        self.plan_table.setRowCount(0)
        root = self.scan_result.root if self.scan_result else None
        for plan_index, plan_item in enumerate(self.plan):
            row = self.plan_table.rowCount()
            self.plan_table.insertRow(row)
            toggle = AeroSwitch()
            toggle.setChecked(plan_item.selected)
            toggle.setAccessibleName(f"Include {plan_item.source.name} in the move plan")
            toggle.toggled.connect(
                lambda checked, idx=plan_index: self._plan_switch_changed(idx, checked)
            )
            toggle_cell = QWidget()
            toggle_layout = QHBoxLayout(toggle_cell)
            toggle_layout.setContentsMargins(0, 0, 0, 0)
            toggle_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            toggle_layout.addWidget(toggle)
            self.plan_table.setCellWidget(row, 0, toggle_cell)
            notes = []
            if plan_item.item_type == "folder":
                notes.append("Project folder · stays together")
            elif plan_item.ai_source == "vision":
                notes.append(f"Image AI: {plan_item.ai_topic} · {plan_item.ai_confidence:.0%}")
            elif plan_item.ai_topic:
                source = "Learned" if plan_item.ai_source == "learned" else (
                    "Your choice" if plan_item.ai_source == "user" else "Suggested"
                )
                score = f" · {plan_item.ai_confidence:.0%} match" if source != "Your choice" else ""
                notes.append(f"{source}: {plan_item.ai_topic}{score}")
            else:
                notes.append("Custom destination" if plan_item.ai_source == "user" else "Category only")
            if plan_item.is_duplicate:
                notes.append("Exact duplicate")
            if plan_item.is_large:
                notes.append("Large")
            current_display = str(plan_item.source.relative_to(root)) if root else str(plan_item.source)
            proposed_display = str(plan_item.destination.relative_to(root)) if root else str(plan_item.destination)
            values = (
                plan_item.category,
                current_display,
                proposed_display,
                _format_size(plan_item.size),
                " · ".join(notes) or "—",
            )
            for col, value in enumerate(values, start=1):
                cell = QTableWidgetItem(value)
                if col == 2:
                    cell.setToolTip(str(plan_item.source))
                elif col == 3:
                    cell.setToolTip(str(plan_item.destination))
                    cell.setFlags(cell.flags() | Qt.ItemFlag.ItemIsEditable)
                else:
                    cell.setToolTip(value)
                self.plan_table.setItem(row, col, cell)
            insight = plan_item.ai_reason or "No strong topical match was found."
            details = [insight]
            if plan_item.ai_topic:
                if plan_item.ai_source == "vision":
                    details.insert(0, f"Image model topic: {plan_item.ai_topic} ({plan_item.ai_confidence:.0%} model score)")
                elif plan_item.ai_source == "project":
                    details.insert(0, "Recognized project folder; its contents remain together.")
                else:
                    score = f" ({plan_item.ai_confidence:.0%} cue match)" if plan_item.ai_source != "user" else ""
                    details.insert(0, f"{plan_item.ai_source.title()} placement: {plan_item.ai_topic}{score}")
            if plan_item.is_duplicate:
                details.append("Exact duplicate content")
            if plan_item.is_large:
                details.append("Large file")
            self.plan_table.item(row, 5).setToolTip("\n".join(details))
        self.plan_table.blockSignals(False)
        self._update_plan_count()
        self.move_button.setEnabled(bool(self.plan))
        if self.plan:
            self.preview_note.setText("Preview only — no files have been changed.")
        elif self.scan_result and self.scan_result.root in self.scan_result.project_directories:
            self.preview_note.setText("This folder is a project. Its contents stay together.")
        else:
            self.preview_note.setText("Everything is already in its category folder.")

    def _handle_plan_edit(self, cell: QTableWidgetItem) -> None:
        if cell.column() != 3 or not self.scan_result:
            return
        row = cell.row()
        if row >= len(self.plan):
            return
        plan_item = self.plan[row]
        root = self.scan_result.root.resolve()
        previous = plan_item.destination
        previous_ai = (plan_item.ai_topic, plan_item.ai_confidence, plan_item.ai_reason, plan_item.ai_source)
        try:
            entered = Path(cell.text().strip())
            if not str(cell.text()).strip():
                raise ValueError("Enter a destination inside the selected folder.")
            proposed = entered if entered.is_absolute() else root / entered
            proposed = proposed.resolve(strict=False)
            proposed.relative_to(root)
            if proposed == plan_item.source.resolve(strict=False):
                raise ValueError("Choose a different destination, or turn this move off.")
            if plan_item.item_type == "folder" and plan_item.source.resolve(strict=False) in proposed.parents:
                raise ValueError("A project folder cannot be moved inside itself.")
            if proposed.exists() and proposed.is_dir():
                proposed = proposed / plan_item.source.name
            if proposed.resolve(strict=False) == plan_item.source.resolve(strict=False):
                raise ValueError("Choose a different destination, or turn this move off.")
            plan_item.destination = proposed
            topic = topic_from_destination(root, plan_item)
            plan_item.ai_topic = topic
            plan_item.ai_source = "user"
            plan_item.ai_confidence = 1.0 if topic else 0.0
            plan_item.ai_reason = (
                f"You chose {topic}; Xortify will remember this approved placement."
                if topic
                else "You adjusted the destination; Xortify will learn a folder label after the move is approved."
            )
            self.plan_table.blockSignals(True)
            cell.setText(str(proposed.relative_to(root)))
            self.plan_table.blockSignals(False)
            cell.setToolTip(str(proposed))
            self._refresh_plan_insight(row)
            self.status_label.setText("Destination updated. The new folder choice will be learned after approval.")
        except (OSError, RuntimeError, ValueError):
            plan_item.destination = previous
            plan_item.ai_topic, plan_item.ai_confidence, plan_item.ai_reason, plan_item.ai_source = previous_ai
            self.plan_table.blockSignals(True)
            cell.setText(str(previous.relative_to(root)))
            cell.setToolTip(str(previous))
            self.plan_table.blockSignals(False)
            self.status_label.setText("Choose a destination inside the selected folder and category plan.")

    def _refresh_plan_insight(self, row: int) -> None:
        plan_item = self.plan[row]
        notes = []
        if plan_item.item_type == "folder":
            notes.append("Project folder · stays together")
        elif plan_item.ai_source == "vision":
            notes.append(f"Image AI: {plan_item.ai_topic} · {plan_item.ai_confidence:.0%}")
        elif plan_item.ai_topic:
            source = "Your choice" if plan_item.ai_source == "user" else (
                "Learned" if plan_item.ai_source == "learned" else "Suggested"
            )
            score = f" · {plan_item.ai_confidence:.0%} match" if source != "Your choice" else ""
            notes.append(f"{source}: {plan_item.ai_topic}{score}")
        else:
            notes.append("Custom destination" if plan_item.ai_source == "user" else "Category only")
        if plan_item.is_duplicate:
            notes.append("Exact duplicate")
        if plan_item.is_large:
            notes.append("Large")
        self.plan_table.item(row, 5).setText(" · ".join(notes))
        details = [plan_item.ai_reason]
        if plan_item.is_duplicate:
            details.append("Exact duplicate content")
        if plan_item.is_large:
            details.append("Large file")
        self.plan_table.item(row, 5).setToolTip("\n".join(details))

    def _plan_switch_changed(self, plan_index: int, selected: bool) -> None:
        if plan_index < len(self.plan):
            self.plan[plan_index].selected = selected
        self._update_plan_count()

    def _update_plan_count(self) -> None:
        selected = sum(item.selected for item in self.plan)
        self.plan_count_label.setText(f"{selected:,} of {len(self.plan):,} proposed moves selected")
        self.move_button.setEnabled(selected > 0)

    def _set_all_plan_checks(self, selected: bool) -> None:
        for row in range(self.plan_table.rowCount()):
            cell = self.plan_table.cellWidget(row, 0)
            toggle = cell.findChild(AeroSwitch) if cell else None
            if toggle:
                toggle.setChecked(selected)

    def _confirm_execute(self) -> None:
        selected = [item for item in self.plan if item.selected]
        if not selected or not self.scan_result:
            return
        answer = QMessageBox.question(
            self,
            "Move approved files?",
            f"Move {len(selected):,} selected item(s) under:\n\n"
            f"{self.scan_result.root}\n\n"
            "Xortify will verify each file or project folder again and journal each move so the latest operation can be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self._start_execute(selected)

    def _start_execute(self, selected: list[PlanItem]) -> None:
        root = self.scan_result.root if self.scan_result else None
        if root is None:
            return
        self._set_busy(True, f"Preparing {len(selected):,} approved move(s)…")
        self.move_button.setEnabled(False)
        self.active_worker = ActionWorker(
            lambda: execute_selected(
                root,
                selected,
                self.database,
                progress_callback=lambda done, total, path: self.active_worker.progress.emit(done, total, str(path)),
            ),
            self,
        )
        self.active_worker.progress.connect(self._action_progress)
        self.active_worker.completed.connect(self._execute_completed)
        self.active_worker.failed.connect(self._worker_failed)
        self.active_worker.start()

    def _start_undo(self) -> None:
        operation = self.database.latest_undoable_operation()
        if not operation:
            QMessageBox.information(self, "Nothing to undo", "There is no completed move operation available.")
            return
        answer = QMessageBox.question(
            self,
            "Undo latest move?",
            f"Restore the moved items from operation #{operation['id']} to their original locations?\n\n"
            "If an original name is now occupied, Xortify will restore the item with a numbered name to avoid overwriting it.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self._set_busy(True, f"Undoing operation #{operation['id']}…")
        self.undo_button.setEnabled(False)
        self.active_worker = ActionWorker(lambda: undo_operation(self.database, int(operation["id"])), self)
        self.active_worker.completed.connect(self._undo_completed)
        self.active_worker.failed.connect(self._worker_failed)
        self.active_worker.start()

    def _action_progress(self, done: int, total: int, path_text: str) -> None:
        self.status_label.setText(f"Processed {done:,} of {total:,} · {path_text}")

    def _execute_completed(self, result: OperationResult) -> None:
        self._set_busy(False)
        self.undo_button.setEnabled(self.database.latest_undoable_operation() is not None)
        self.move_button.setEnabled(False)
        self.preview_note.setText(f"Operation #{result.operation_id} finished. Scan again to refresh this snapshot.")
        self.status_label.setText(
            f"Moved {result.moved:,} item(s). {len(result.failed):,} move(s) need attention."
        )
        self._refresh_history()
        noun = "placement" if result.learned == 1 else "placements"
        learned_note = f"\nLearned from {result.learned} approved {noun}." if result.learned else ""
        QMessageBox.information(
            self,
            "Organization complete",
            f"Moved {result.moved:,} item(s).\nCould not move: {len(result.failed):,}.{learned_note}",
        )
        if result.learned:
            self.status_label.setText(
                f"Moved {result.moved:,} item(s). Learned from {result.learned:,} approved {noun}."
            )

    def _undo_completed(self, result: UndoResult) -> None:
        self._set_busy(False)
        self.undo_button.setEnabled(self.database.latest_undoable_operation() is not None)
        self.status_label.setText(
            f"Restored {result.restored:,} file(s). {len(result.failed):,} restore(s) need attention."
        )
        self.preview_note.setText(f"Operation #{result.operation_id} was undone. Scan again to refresh this snapshot.")
        self._refresh_history()
        QMessageBox.information(
            self,
            "Undo complete",
            f"Restored {result.restored:,} item(s).\nCould not restore: {len(result.failed):,}.",
        )

    def _worker_failed(self, message: str) -> None:
        self._set_busy(False)
        self.move_button.setEnabled(bool(self.plan))
        self.undo_button.setEnabled(self.database.latest_undoable_operation() is not None)
        self.status_label.setText("The requested action could not be completed.")
        QMessageBox.critical(self, "Xortify could not complete that action", message)

    def _refresh_history(self) -> None:
        self.history_table.setRowCount(0)
        for operation in self.database.recent_operations():
            row = self.history_table.rowCount()
            self.history_table.insertRow(row)
            created = str(operation["created_at"]).replace("T", " ")[:19]
            values = (created, str(operation["root"]), "Organization", str(operation["status"]))
            for col, value in enumerate(values):
                cell = QTableWidgetItem(value)
                cell.setToolTip(value)
                self.history_table.setItem(row, col, cell)


def create_application() -> QApplication:
    app = QApplication.instance() or QApplication([])
    app.setApplicationName("Xortify")
    app.setOrganizationName("Xortify")
    app.setStyle("Fusion")
    return app
