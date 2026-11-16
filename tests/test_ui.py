from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from xortify.database import XortifyDatabase
from xortify.main_window import AeroSwitch, MainWindow
from xortify.planner import build_plan
from xortify.scanner import scan_directory


class MainWindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setStyle("Fusion")

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.base = Path(self.temporary.name)
        self.root = self.base / "Weekend photos"
        self.root.mkdir()
        (self.root / "lake.png").write_bytes(b"\x89PNG\r\n\x1a\nwater")
        self.window = MainWindow(XortifyDatabase(self.base / "state.sqlite3"))
        result = scan_directory(self.root)
        self.window.scan_result = result
        self.window.plan = build_plan(result)
        self.window._populate_plan()
        self.window.show()
        self.app.processEvents()

    def tearDown(self) -> None:
        self.window.close()
        self.temporary.cleanup()

    def test_plan_shows_root_relative_paths_and_full_path_tooltips(self) -> None:
        self.assertEqual(self.window.plan_table.item(0, 2).text(), "lake.png")
        self.assertEqual(self.window.plan_table.item(0, 3).text(), str(Path("Images") / "lake.png"))
        self.assertEqual(self.window.plan_table.item(0, 2).toolTip(), str(self.root / "lake.png"))

    def test_aero_switch_updates_plan_and_select_all_control(self) -> None:
        cell = self.window.plan_table.cellWidget(0, 0)
        switch = cell.findChild(AeroSwitch)
        self.assertIsNotNone(switch)
        self.assertTrue(switch.isChecked())

        QTest.mouseClick(switch, Qt.MouseButton.LeftButton)
        self.app.processEvents()
        self.assertFalse(self.window.plan[0].selected)
        self.assertFalse(self.window.move_button.isEnabled())

        self.window._set_all_plan_checks(True)
        self.assertTrue(self.window.plan[0].selected)
        self.assertTrue(self.window.move_button.isEnabled())

    def test_proposed_destination_edit_is_validated_and_labeled(self) -> None:
        destination = self.window.plan_table.item(0, 3)
        destination.setText(str(Path("Images") / "Trips" / "lake.png"))
        self.app.processEvents()
        self.assertEqual(
            self.window.plan[0].destination,
            self.root / "Images" / "Trips" / "lake.png",
        )
        self.assertEqual(self.window.plan[0].ai_topic, "Trips")
        self.assertEqual(self.window.plan[0].ai_source, "user")


if __name__ == "__main__":
    unittest.main()
