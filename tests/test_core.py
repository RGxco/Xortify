from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

from xortify.classifier import classify_file, classify_header
from xortify.database import XortifyDatabase
from xortify.intelligence import LocalPlacementAssistant
from xortify.operations import execute_selected, undo_operation
from xortify.planner import build_plan
from xortify.scanner import scan_directory
from xortify.vision import image_model_installed, topic_for_class


PNG_HEADER = b"\x89PNG\r\n\x1a\n" + b"tiny-image-payload"


class ClassifierTests(unittest.TestCase):
    def test_signature_takes_precedence_over_misleading_extension(self) -> None:
        category, mime = classify_header(PNG_HEADER, ".txt")
        self.assertEqual(category, "Images")
        self.assertEqual(mime, "image/png")

    def test_package_document_extension_is_not_misclassified_as_archive(self) -> None:
        category, _mime = classify_header(b"PK\x03\x04fake-office-package", ".docx")
        self.assertEqual(category, "Documents")

    def test_local_name_cues_suggest_a_topical_subfolder(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            inbox = root / "inbox"
            inbox.mkdir()
            (inbox / "invoice_2025.pdf").write_bytes(b"local sample")
            plan = build_plan(scan_directory(root), LocalPlacementAssistant())
            self.assertEqual(len(plan), 1)
            self.assertEqual(plan[0].ai_topic, "Receipts")
            self.assertIn("Filename cue", plan[0].ai_reason)
            self.assertEqual(
                plan[0].destination.relative_to(root),
                Path("Documents") / "Receipts" / "inbox" / "invoice_2025.pdf",
            )

    def test_extension_and_mime_fallbacks(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            script = root / "tool.py"
            script.write_text("print('local')", encoding="utf-8")
            self.assertEqual(classify_file(script)[0], "Code")

            unknown_text = root / "notes.unknownformat"
            unknown_text.write_text("plain text", encoding="utf-8")
            self.assertEqual(classify_file(unknown_text)[0], "Other")


class LocalImageAITests(unittest.TestCase):
    def test_image_model_groups_cat_and_dog_classes(self) -> None:
        self.assertEqual(topic_for_class(281, "tabby"), "Cats")
        self.assertEqual(topic_for_class(284, "Siamese cat"), "Cats")
        self.assertEqual(topic_for_class(207, "golden retriever"), "Dogs")
        self.assertEqual(topic_for_class(25, "European fire salamander"), "Animals")

    def test_non_animal_classes_use_broad_subject_folders(self) -> None:
        self.assertEqual(topic_for_class(951, "lemon"), "Food")
        self.assertEqual(topic_for_class(404, "airliner"), "Vehicles")
        self.assertEqual(topic_for_class(980, "volcano"), "Nature")
        self.assertIsNone(topic_for_class(900, "carton"))

    def test_downloaded_model_runs_offline_when_optional_stack_is_installed(self) -> None:
        if not image_model_installed():
            self.skipTest("The optional image model has not been downloaded.")
        try:
            from PIL import Image
            from xortify.vision import LocalImageClassifier
        except ImportError:
            self.skipTest("Install the optional vision dependencies to run this check.")
        with tempfile.TemporaryDirectory() as directory:
            image_path = Path(directory) / "sample.png"
            Image.new("RGB", (256, 160), color=(120, 175, 80)).save(image_path)
            prediction = LocalImageClassifier().predict(image_path)
        self.assertTrue(prediction.label)
        self.assertGreaterEqual(prediction.class_index, 0)
        self.assertLess(prediction.class_index, 1000)


class ScanAndOperationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.base = Path(self.temporary.name)
        self.root = self.base / "collection"
        self.root.mkdir()
        self.database = XortifyDatabase(self.base / "state" / "xortify.sqlite3")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_scan_is_read_only_and_reports_findings(self) -> None:
        nested = self.root / "inbox"
        nested.mkdir()
        (self.root / "empty").mkdir()
        first = nested / "photo.png"
        second = self.root / "copy.bin"
        first.write_bytes(PNG_HEADER)
        second.write_bytes(PNG_HEADER)
        (self.root / "large.bin").write_bytes(b"x" * 40)

        before = {
            path.relative_to(self.root): (path.stat().st_mtime_ns, path.read_bytes() if path.is_file() else None)
            for path in self.root.rglob("*")
        }
        result = scan_directory(self.root, large_file_threshold=30)
        after = {
            path.relative_to(self.root): (path.stat().st_mtime_ns, path.read_bytes() if path.is_file() else None)
            for path in self.root.rglob("*")
        }

        self.assertEqual(before, after)
        self.assertEqual(len(result.files), 3)
        self.assertEqual(len(result.duplicate_groups), 1)
        self.assertEqual(result.duplicate_file_count, 2)
        self.assertEqual([p.name for p in result.empty_directories], ["empty"])
        self.assertEqual([record.path.name for record in result.large_files], ["large.bin"])
        scan_id = self.database.record_scan(result)
        self.assertGreater(scan_id, 0)

    def test_plan_handles_existing_destination_and_undoes_selected_moves(self) -> None:
        incoming = self.root / "incoming" / "photo.png"
        occupied = self.root / "Images" / "incoming" / "photo.png"
        incoming.parent.mkdir(parents=True)
        occupied.parent.mkdir(parents=True)
        incoming.write_bytes(PNG_HEADER)
        occupied.write_bytes(b"keep this existing file")

        scan = scan_directory(self.root)
        plan = build_plan(scan)
        self.assertEqual(len(plan), 1)
        self.assertEqual(plan[0].destination.name, "photo (2).png")
        self.assertFalse(occupied.read_bytes() == incoming.read_bytes())

        result = execute_selected(self.root, plan, self.database)
        self.assertEqual(result.moved, 1)
        moved_path = plan[0].destination.with_name("photo (2).png")
        self.assertTrue(moved_path.exists())
        self.assertFalse(incoming.exists())
        self.assertTrue(occupied.exists())

        # A newly created file at the original path must not be overwritten by undo.
        incoming.write_bytes(b"new file created after moving")
        undo = undo_operation(self.database, result.operation_id)
        self.assertEqual(undo.restored, 1)
        self.assertEqual(incoming.read_bytes(), b"new file created after moving")
        restored_alternative = incoming.with_name("photo (2).png")
        self.assertEqual(restored_alternative.read_bytes(), PNG_HEADER)
        self.assertTrue(occupied.exists())

    def test_changed_source_is_rejected_without_moving_it(self) -> None:
        source = self.root / "notes.txt"
        source.write_text("original", encoding="utf-8")
        plan = build_plan(scan_directory(self.root))
        source.write_text("changed after scan", encoding="utf-8")

        result = execute_selected(self.root, plan, self.database)
        self.assertEqual(result.moved, 0)
        self.assertEqual(len(result.failed), 1)
        self.assertTrue(source.exists())
        self.assertEqual(source.read_text(encoding="utf-8"), "changed after scan")
        self.assertIsNone(self.database.latest_undoable_operation())

    def test_exact_sha256_is_recorded_for_each_file(self) -> None:
        source = self.root / "data.bin"
        source.write_bytes(b"sample")
        record = scan_directory(self.root).files[0]
        self.assertEqual(record.sha256, hashlib.sha256(b"sample").hexdigest())

    def test_startup_reconciles_an_interrupted_undo(self) -> None:
        source = self.root / "inbox" / "notes.txt"
        source.parent.mkdir()
        source.write_text("journal recovery", encoding="utf-8")
        plan = build_plan(scan_directory(self.root))
        moved = execute_selected(self.root, plan, self.database)
        entry = self.database.get_operation_items(moved.operation_id)[0]
        destination = Path(str(entry["destination_path"]))

        self.database.set_operation_state(moved.operation_id, "undoing")
        self.database.update_operation_item(int(entry["id"]), "undoing", undo_path=source)
        destination.rename(source)

        recovered_database = XortifyDatabase(self.database.path)
        recovered_entry = recovered_database.get_operation_items(moved.operation_id)[0]
        recovered_operation = recovered_database.get_operation(moved.operation_id)
        self.assertEqual(recovered_entry["status"], "undone")
        self.assertEqual(recovered_operation["status"], "undone")
        self.assertIsNone(recovered_database.latest_undoable_operation())
        self.assertEqual(source.read_text(encoding="utf-8"), "journal recovery")

    def test_approved_custom_destination_teaches_future_suggestions(self) -> None:
        source = self.root / "incoming" / "client_alpha.pdf"
        source.parent.mkdir()
        source.write_bytes(b"sample client document")
        plan = build_plan(scan_directory(self.root))
        plan[0].destination = self.root / "Documents" / "Client Work" / "incoming" / source.name

        result = execute_selected(self.root, plan, self.database)
        self.assertEqual(result.moved, 1)
        self.assertEqual(result.learned, 1)
        self.assertEqual(self.database.placement_example_count(), 1)

        next_source = self.root / "incoming" / "client_beta.pdf"
        next_source.write_bytes(b"another client document")
        next_plan = build_plan(
            scan_directory(self.root),
            LocalPlacementAssistant(self.database.recent_placement_examples()),
        )
        learned_plan = next(item for item in next_plan if item.source == next_source)
        self.assertEqual(learned_plan.ai_topic, "Client Work")
        self.assertEqual(learned_plan.ai_source, "learned")

    def test_recognized_project_moves_and_undoes_as_one_folder(self) -> None:
        project = self.root / "incoming" / "tiny-app"
        (project / "src").mkdir(parents=True)
        (project / "pyproject.toml").write_text("[project]\nname='tiny-app'", encoding="utf-8")
        (project / "src" / "main.py").write_text("print('kept together')", encoding="utf-8")
        (project / "src" / "native.dll").write_bytes(b"binary")

        scan = scan_directory(self.root)
        self.assertEqual(scan.project_directories, [project])
        plan = build_plan(scan)
        self.assertEqual(len(plan), 1)
        self.assertEqual(plan[0].item_type, "folder")
        self.assertEqual(plan[0].destination.relative_to(self.root), Path("Code") / "Projects" / "tiny-app")
        self.assertEqual(plan[0].size, sum(path.stat().st_size for path in project.rglob("*") if path.is_file()))

        result = execute_selected(self.root, plan, self.database)
        moved_project = self.root / "Code" / "Projects" / "tiny-app"
        self.assertEqual(result.moved, 1)
        self.assertFalse(project.exists())
        self.assertTrue((moved_project / "src" / "main.py").exists())
        self.assertTrue((moved_project / "src" / "native.dll").exists())
        self.assertEqual(self.database.get_operation_items(result.operation_id)[0]["item_type"], "folder")

        undo = undo_operation(self.database, result.operation_id)
        self.assertEqual(undo.restored, 1)
        self.assertTrue((project / "src" / "main.py").exists())
        self.assertTrue((project / "src" / "native.dll").exists())

    def test_selected_project_root_protects_all_its_files(self) -> None:
        (self.root / "pyproject.toml").write_text("[project]\nname='root'", encoding="utf-8")
        (self.root / "loose.py").write_text("print('stay')", encoding="utf-8")
        scan = scan_directory(self.root)
        self.assertEqual(scan.project_directories, [self.root])
        self.assertEqual(build_plan(scan), [])

    def test_changed_project_is_rejected_without_moving_it(self) -> None:
        project = self.root / "incoming" / "tiny-app"
        project.mkdir(parents=True)
        (project / "pyproject.toml").write_text("[project]\nname='tiny-app'", encoding="utf-8")
        source = project / "main.py"
        source.write_text("print('original')", encoding="utf-8")
        plan = build_plan(scan_directory(self.root))
        source.write_text("print('changed after scan')", encoding="utf-8")

        result = execute_selected(self.root, plan, self.database)
        self.assertEqual(result.moved, 0)
        self.assertEqual(len(result.failed), 1)
        self.assertTrue(source.exists())
        self.assertFalse((self.root / "Code" / "Projects" / "tiny-app").exists())

    def test_project_folder_collision_keeps_both_directories(self) -> None:
        project = self.root / "incoming" / "tiny-app"
        project.mkdir(parents=True)
        (project / "pyproject.toml").write_text("[project]\nname='tiny-app'", encoding="utf-8")
        (project / "main.py").write_text("print('new')", encoding="utf-8")
        occupied = self.root / "Code" / "Projects" / "tiny-app"
        occupied.mkdir(parents=True)
        (occupied / "keep.txt").write_text("existing", encoding="utf-8")

        plan = [item for item in build_plan(scan_directory(self.root)) if item.item_type == "folder"]
        self.assertEqual(plan[0].destination.name, "tiny-app (2)")
        result = execute_selected(self.root, plan, self.database)
        moved_project = self.root / "Code" / "Projects" / "tiny-app (2)"
        self.assertEqual(result.moved, 1)
        self.assertEqual((occupied / "keep.txt").read_text(encoding="utf-8"), "existing")
        self.assertTrue((moved_project / "main.py").exists())


if __name__ == "__main__":
    unittest.main()
