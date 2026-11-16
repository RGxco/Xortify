"""Read-only recursive directory scan and SHA-256 duplicate detection."""

from __future__ import annotations

import hashlib
import os
import stat as stat_module
import threading
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Callable

from .classifier import classify_file
from .bundles import project_marker
from .models import FileRecord, ScanResult

ProgressCallback = Callable[[int, Path], None]


def _is_link_or_reparse(path: Path) -> bool:
    if path.is_symlink():
        return True
    try:
        attributes = getattr(path.lstat(), "st_file_attributes", 0)
        reparse_flag = getattr(stat_module, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
        return bool(attributes & reparse_flag)
    except OSError:
        return True


def _sha256(path: Path, cancel_event: threading.Event | None = None) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while True:
            if cancel_event and cancel_event.is_set():
                raise InterruptedError("Scan cancelled")
            block = stream.read(1024 * 1024)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def scan_directory(
    root: Path | str,
    *,
    large_file_threshold: int = 500 * 1024 * 1024,
    progress_callback: ProgressCallback | None = None,
    cancel_event: threading.Event | None = None,
) -> ScanResult:
    """Scan files without changing them. Symbolic links are not followed."""
    root_path = Path(root).expanduser().resolve(strict=True)
    if not root_path.is_dir():
        raise NotADirectoryError(f"Selected path is not a directory: {root_path}")
    if large_file_threshold < 0:
        raise ValueError("large_file_threshold must be zero or greater")

    result = ScanResult(root=root_path, started_at=datetime.now().astimezone())
    by_hash: dict[str, list[FileRecord]] = defaultdict(list)
    project_candidates: list[Path] = []

    def on_walk_error(error: OSError) -> None:
        path = Path(error.filename) if error.filename else root_path
        result.unreadable_files.append((path, str(error)))

    for current_text, dirnames, filenames in os.walk(root_path, topdown=True, followlinks=False, onerror=on_walk_error):
        if cancel_event and cancel_event.is_set():
            raise InterruptedError("Scan cancelled")
        current = Path(current_text)
        was_empty = current != root_path and not dirnames and not filenames
        # Prune links and junction-like entries so scans stay inside the chosen tree.
        dirnames[:] = sorted(name for name in dirnames if not _is_link_or_reparse(current / name))
        filenames = sorted(filenames, key=str.casefold)
        if project_marker(filenames, dirnames):
            project_candidates.append(current)
        if was_empty:
            result.empty_directories.append(current)

        for filename in filenames:
            path = current / filename
            if _is_link_or_reparse(path):
                continue
            try:
                stat = path.stat(follow_symlinks=False)
                if not path.is_file():
                    continue
                with path.open("rb") as stream:
                    header = stream.read(8192)
                category, mime_type = classify_file(path, header)
                record = FileRecord(
                    path=path,
                    relative_path=path.relative_to(root_path),
                    size=stat.st_size,
                    modified_at=datetime.fromtimestamp(stat.st_mtime).astimezone(),
                    category=category,
                    mime_type=mime_type,
                    sha256=_sha256(path, cancel_event),
                )
                result.files.append(record)
                by_hash[record.sha256].append(record)
                if record.size >= large_file_threshold and record.size > 0:
                    result.large_files.append(record)
                if progress_callback:
                    progress_callback(len(result.files), path)
            except InterruptedError:
                raise
            except (OSError, PermissionError) as error:
                result.unreadable_files.append((path, str(error)))

    result.duplicate_groups = [group for group in by_hash.values() if len(group) > 1]
    result.duplicate_groups.sort(key=lambda group: group[0].sha256)
    result.files.sort(key=lambda item: str(item.relative_path).casefold())
    # An outer project is moved as one unit, so nested project markers belong
    # to that unit and must never create overlapping plan entries.
    for candidate in sorted(project_candidates, key=lambda path: (len(path.parts), str(path).casefold())):
        if not any(parent == candidate or parent in candidate.parents for parent in result.project_directories):
            result.project_directories.append(candidate)
    result.empty_directories.sort(key=lambda item: str(item).casefold())
    result.large_files.sort(key=lambda item: (-item.size, str(item.relative_path).casefold()))
    result.finished_at = datetime.now().astimezone()
    return result
