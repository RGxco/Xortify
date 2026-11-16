"""Collision-safe file moves and journal-backed rollback/undo."""

from __future__ import annotations

import hashlib
import os
import shutil
from pathlib import Path
from typing import Callable

from .database import XortifyDatabase
from .bundles import fingerprint_directory
from .intelligence import placement_features, topic_from_destination
from .models import OperationResult, PlanItem, UndoResult

ProgressCallback = Callable[[int, int, Path], None]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _inside_root(path: Path, root: Path) -> Path:
    resolved = path.resolve(strict=False)
    try:
        resolved.relative_to(root)
    except ValueError as error:
        raise ValueError(f"Path is outside the selected folder: {path}") from error
    return resolved


def _available_path(path: Path) -> Path:
    candidate = path
    index = 2
    while candidate.exists() or candidate.is_symlink():
        candidate = path.with_name(f"{path.stem} ({index}){path.suffix}")
        index += 1
    return candidate


def _safe_move(source: Path, destination: Path) -> None:
    """Move one file without replacing an existing destination."""
    if destination.exists() or destination.is_symlink():
        raise FileExistsError(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)

    if os.name == "nt":
        # Windows rename fails when the target already exists and is atomic on
        # the same volume. The selected root contains both operation paths.
        os.rename(source, destination)
        return

    try:
        # An exclusive hard-link creation gives POSIX the same no-overwrite
        # property. Source and destination are on the selected volume.
        os.link(source, destination, follow_symlinks=False)
        try:
            source.unlink()
        except OSError:
            destination.unlink(missing_ok=True)
            raise
        return
    except FileExistsError:
        raise
    except OSError:
        # Some filesystems do not support hard links. Copy into an exclusively
        # created file, verify it, then remove the source; never clobber data.
        created_destination = False
        try:
            with source.open("rb") as input_stream, destination.open("xb") as output_stream:
                created_destination = True
                shutil.copyfileobj(input_stream, output_stream, length=1024 * 1024)
                output_stream.flush()
                os.fsync(output_stream.fileno())
            shutil.copystat(source, destination, follow_symlinks=False)
            if _sha256(source) != _sha256(destination):
                raise OSError("Destination verification failed; source was kept.")
            source.unlink()
        except OSError:
            if created_destination:
                destination.unlink(missing_ok=True)
            raise


def _safe_move_directory(source: Path, destination: Path) -> None:
    """Rename a project directory as one unit without replacing anything."""
    if destination.exists() or destination.is_symlink():
        raise FileExistsError(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    # Both paths are under the selected root, so a directory rename stays on
    # the same volume and preserves every nested file and empty directory.
    os.rename(source, destination)


def execute_selected(
    root: Path | str,
    items: list[PlanItem],
    database: XortifyDatabase,
    progress_callback: ProgressCallback | None = None,
) -> OperationResult:
    selected = [item for item in items if item.selected]
    if not selected:
        raise ValueError("Select at least one proposed move.")
    root_path = Path(root).expanduser().resolve(strict=True)
    if not root_path.is_dir():
        raise NotADirectoryError(root_path)
    operation_id, item_ids = database.begin_operation(root_path, selected)
    moved = 0
    learned = 0
    failed: list[tuple[Path, str]] = []

    for index, item in enumerate(selected):
        source = Path(item.source)
        try:
            actual_source = _inside_root(source, root_path)
            if item.item_type == "folder":
                if source.is_symlink() or not actual_source.is_dir():
                    raise FileNotFoundError("Project folder is missing or is no longer a regular folder.")
                if fingerprint_directory(actual_source) != item.sha256:
                    raise RuntimeError("Project contents changed after the scan; rescan before moving it.")
            else:
                if source.is_symlink() or not actual_source.is_file():
                    raise FileNotFoundError("Source is missing or is no longer a regular file.")
                if _sha256(actual_source) != item.sha256:
                    raise RuntimeError("File contents changed after the scan; rescan before moving it.")

            desired = Path(item.destination)
            _inside_root(desired, root_path)
            if item.item_type == "folder" and actual_source in desired.resolve(strict=False).parents:
                raise ValueError("A project folder cannot be moved inside itself.")
            if desired.resolve(strict=False) == actual_source:
                raise ValueError("The destination cannot be the source path.")
            destination = _available_path(desired)
            _inside_root(destination, root_path)
            # Recheck after parent creation so existing symlinks cannot redirect
            # a proposed move outside the selected directory.
            destination.parent.mkdir(parents=True, exist_ok=True)
            _inside_root(destination, root_path)

            database.update_operation_item(
                item_ids[index], "moving", destination_path=destination
            )
            if item.item_type == "folder":
                _safe_move_directory(actual_source, destination)
            else:
                _safe_move(actual_source, destination)
            moved += 1
            database.update_operation_item(item_ids[index], "moved")
            topic = topic_from_destination(root_path, item) if item.item_type == "file" else None
            if topic:
                try:
                    database.add_placement_example(
                        item.category,
                        placement_features(item.category, item.source.name, item.relative_path),
                        topic,
                    )
                    learned += 1
                except Exception:
                    # Keep the confirmed file move and its journal state even
                    # if optional local learning storage is temporarily busy.
                    pass
        except Exception as error:  # Each file is isolated; later approved files can proceed.
            message = str(error)
            failed.append((source, message))
            database.update_operation_item(item_ids[index], "failed", error=message)
        if progress_callback:
            progress_callback(index + 1, len(selected), source)

    status = "completed" if not failed else ("partial" if moved else "failed")
    database.finish_operation(operation_id, status)
    return OperationResult(operation_id=operation_id, moved=moved, failed=failed, learned=learned)


def undo_operation(database: XortifyDatabase, operation_id: int | None = None) -> UndoResult:
    operation = database.get_operation(operation_id) if operation_id is not None else database.latest_undoable_operation()
    if not operation:
        raise ValueError("There is no completed file operation available to undo.")
    if operation["status"] not in {"completed", "partial", "undo_partial"}:
        raise ValueError(f"Operation #{operation['id']} is not ready to undo.")
    operation_id = int(operation["id"])
    database.set_operation_state(operation_id, "undoing")
    root = Path(str(operation["root"])).resolve(strict=True)
    entries = database.get_operation_items(operation_id)
    restored = 0
    failed: list[tuple[Path, str]] = []

    for entry in reversed(entries):
        if entry["status"] not in {"moved", "undo_failed"}:
            continue
        original = Path(str(entry["source_path"]))
        current = Path(str(entry["destination_path"]))
        item_type = str(entry.get("item_type", "file"))
        try:
            actual_current = _inside_root(current, root)
            if current.is_symlink() or (
                not actual_current.is_dir() if item_type == "folder" else not actual_current.is_file()
            ):
                raise FileNotFoundError(f"Moved item is missing: {current}")
            _inside_root(original, root)
            restore_to = _available_path(original)
            restore_to.parent.mkdir(parents=True, exist_ok=True)
            _inside_root(restore_to, root)
            database.update_operation_item(int(entry["id"]), "undoing", undo_path=restore_to)
            if item_type == "folder":
                _safe_move_directory(actual_current, restore_to)
            else:
                _safe_move(actual_current, restore_to)
            database.update_operation_item(
                int(entry["id"]), "undone", undo_path=restore_to
            )
            restored += 1
        except Exception as error:
            message = str(error)
            failed.append((current, message))
            database.update_operation_item(int(entry["id"]), "undo_failed", error=message)

    status = "undone" if not failed else "undo_partial"
    database.finish_operation(operation_id, status)
    return UndoResult(operation_id=operation_id, restored=restored, failed=failed)
