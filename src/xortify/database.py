"""SQLite persistence for scan snapshots and reversible file operations."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Iterator

from .models import PlanItem, ScanResult


class XortifyDatabase:
    def __init__(self, path: Path | str):
        self.path = Path(path).expanduser()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 30000")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self._connection() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS scans (
                    id INTEGER PRIMARY KEY,
                    root TEXT NOT NULL,
                    started_at TEXT,
                    finished_at TEXT,
                    file_count INTEGER NOT NULL,
                    empty_directory_count INTEGER NOT NULL,
                    duplicate_group_count INTEGER NOT NULL,
                    large_file_count INTEGER NOT NULL,
                    unreadable_file_count INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS scan_files (
                    id INTEGER PRIMARY KEY,
                    scan_id INTEGER NOT NULL REFERENCES scans(id) ON DELETE CASCADE,
                    path TEXT NOT NULL,
                    relative_path TEXT NOT NULL,
                    size INTEGER NOT NULL,
                    modified_at TEXT NOT NULL,
                    category TEXT NOT NULL,
                    mime_type TEXT,
                    sha256 TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_scan_files_sha256 ON scan_files(scan_id, sha256);
                CREATE TABLE IF NOT EXISTS empty_directories (
                    id INTEGER PRIMARY KEY,
                    scan_id INTEGER NOT NULL REFERENCES scans(id) ON DELETE CASCADE,
                    path TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS operations (
                    id INTEGER PRIMARY KEY,
                    root TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    completed_at TEXT,
                    status TEXT NOT NULL,
                    error TEXT
                );
                CREATE TABLE IF NOT EXISTS operation_items (
                    id INTEGER PRIMARY KEY,
                    operation_id INTEGER NOT NULL REFERENCES operations(id) ON DELETE CASCADE,
                    source_path TEXT NOT NULL,
                    destination_path TEXT NOT NULL,
                    relative_path TEXT NOT NULL,
                    size INTEGER NOT NULL,
                    sha256 TEXT NOT NULL,
                    category TEXT NOT NULL,
                    item_type TEXT NOT NULL DEFAULT 'file',
                    status TEXT NOT NULL,
                    error TEXT,
                    undo_path TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_operation_items_operation ON operation_items(operation_id, id);
                CREATE TABLE IF NOT EXISTS placement_examples (
                    id INTEGER PRIMARY KEY,
                    category TEXT NOT NULL,
                    features TEXT NOT NULL,
                    topic TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_placement_examples_category ON placement_examples(category, id);
                """
            )
            item_columns = {
                str(row["name"]) for row in connection.execute("PRAGMA table_info(operation_items)")
            }
            if "item_type" not in item_columns:
                connection.execute(
                    "ALTER TABLE operation_items ADD COLUMN item_type TEXT NOT NULL DEFAULT 'file'"
                )
        self.reconcile_inflight()

    def add_placement_example(self, category: str, features: list[str], topic: str) -> None:
        normalized_features = " ".join(sorted(set(features)))
        normalized_topic = topic.strip()
        if not normalized_features or not normalized_topic:
            return
        with self._connection() as connection:
            connection.execute(
                "INSERT INTO placement_examples (category, features, topic, created_at) VALUES (?, ?, ?, ?)",
                (category, normalized_features, normalized_topic, datetime.now().astimezone().isoformat()),
            )
            connection.execute(
                "DELETE FROM placement_examples WHERE id NOT IN (SELECT id FROM placement_examples ORDER BY id DESC LIMIT 500)"
            )

    def recent_placement_examples(self, limit: int = 500) -> list[dict[str, object]]:
        limit = max(1, min(500, int(limit)))
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT category, features, topic FROM placement_examples ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def placement_example_count(self) -> int:
        with self._connection() as connection:
            row = connection.execute("SELECT COUNT(*) AS count FROM placement_examples").fetchone()
        return int(row["count"])

    def record_scan(self, result: ScanResult) -> int:
        with self._connection() as connection:
            cursor = connection.execute(
                """INSERT INTO scans
                   (root, started_at, finished_at, file_count, empty_directory_count,
                    duplicate_group_count, large_file_count, unreadable_file_count)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    str(result.root),
                    result.started_at.isoformat() if result.started_at else None,
                    result.finished_at.isoformat() if result.finished_at else None,
                    len(result.files),
                    len(result.empty_directories),
                    len(result.duplicate_groups),
                    len(result.large_files),
                    len(result.unreadable_files),
                ),
            )
            scan_id = int(cursor.lastrowid)
            connection.executemany(
                """INSERT INTO scan_files
                   (scan_id, path, relative_path, size, modified_at, category, mime_type, sha256)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                [
                    (
                        scan_id,
                        str(record.path),
                        str(record.relative_path),
                        record.size,
                        record.modified_at.isoformat(),
                        record.category,
                        record.mime_type,
                        record.sha256,
                    )
                    for record in result.files
                ],
            )
            connection.executemany(
                "INSERT INTO empty_directories (scan_id, path) VALUES (?, ?)",
                [(scan_id, str(path)) for path in result.empty_directories],
            )
        return scan_id

    def begin_operation(self, root: Path, items: list[PlanItem]) -> tuple[int, dict[int, int]]:
        now = datetime.now().astimezone().isoformat()
        with self._connection() as connection:
            cursor = connection.execute(
                "INSERT INTO operations (root, created_at, status) VALUES (?, ?, 'running')",
                (str(root), now),
            )
            operation_id = int(cursor.lastrowid)
            item_ids: dict[int, int] = {}
            for index, item in enumerate(items):
                row = connection.execute(
                    """INSERT INTO operation_items
                       (operation_id, source_path, destination_path, relative_path, size,
                        sha256, category, item_type, status)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending')""",
                    (
                        operation_id,
                        str(item.source),
                        str(item.destination),
                        str(item.relative_path),
                        item.size,
                        item.sha256,
                        item.category,
                        item.item_type,
                    ),
                )
                item_ids[index] = int(row.lastrowid)
        return operation_id, item_ids

    def update_operation_item(
        self,
        item_id: int,
        status: str,
        *,
        error: str | None = None,
        destination_path: Path | None = None,
        undo_path: Path | None = None,
    ) -> None:
        fields = ["status = ?", "error = ?"]
        values: list[object] = [status, error]
        if destination_path is not None:
            fields.append("destination_path = ?")
            values.append(str(destination_path))
        if undo_path is not None:
            fields.append("undo_path = ?")
            values.append(str(undo_path))
        values.append(item_id)
        with self._connection() as connection:
            connection.execute(f"UPDATE operation_items SET {', '.join(fields)} WHERE id = ?", values)

    def finish_operation(self, operation_id: int, status: str, error: str | None = None) -> None:
        with self._connection() as connection:
            connection.execute(
                "UPDATE operations SET status = ?, completed_at = ?, error = ? WHERE id = ?",
                (status, datetime.now().astimezone().isoformat(), error, operation_id),
            )

    def set_operation_state(self, operation_id: int, status: str, error: str | None = None) -> None:
        with self._connection() as connection:
            connection.execute(
                "UPDATE operations SET status = ?, error = ? WHERE id = ?",
                (status, error, operation_id),
            )

    def get_operation(self, operation_id: int) -> dict[str, object] | None:
        with self._connection() as connection:
            row = connection.execute("SELECT * FROM operations WHERE id = ?", (operation_id,)).fetchone()
        return dict(row) if row else None

    def get_operation_items(self, operation_id: int) -> list[dict[str, object]]:
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT * FROM operation_items WHERE operation_id = ? ORDER BY id",
                (operation_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def latest_undoable_operation(self) -> dict[str, object] | None:
        with self._connection() as connection:
            row = connection.execute(
                """SELECT * FROM operations
                   WHERE status IN ('completed', 'partial', 'undo_partial')
                   ORDER BY id DESC LIMIT 1"""
            ).fetchone()
        return dict(row) if row else None

    def recent_operations(self, limit: int = 10) -> list[dict[str, object]]:
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT * FROM operations ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(row) for row in rows]

    def reconcile_inflight(self) -> None:
        """Resolve journal entries interrupted between intent and move completion."""
        with self._connection() as connection:
            rows = connection.execute(
                """SELECT oi.id, oi.source_path, oi.destination_path, oi.undo_path,
                          oi.status AS item_status, oi.operation_id, o.status AS operation_status
                   FROM operation_items oi JOIN operations o ON o.id = oi.operation_id
                   WHERE oi.status IN ('moving', 'undoing') OR o.status IN ('running', 'undoing')"""
            ).fetchall()
            running_operations: set[int] = set()
            undoing_operations: set[int] = set()
            for row in rows:
                operation_id = int(row["operation_id"])
                if row["operation_status"] == "undoing":
                    undoing_operations.add(operation_id)
                elif row["operation_status"] == "running":
                    running_operations.add(operation_id)
                if row["id"] is None or row["item_status"] not in {"moving", "undoing"}:
                    continue
                item_id = int(row["id"])
                source = Path(row["source_path"])
                destination = Path(row["destination_path"])
                if row["item_status"] == "moving":
                    if not source.exists() and destination.exists():
                        connection.execute(
                            "UPDATE operation_items SET status = 'moved', error = NULL WHERE id = ?",
                            (item_id,),
                        )
                    else:
                        connection.execute(
                            "UPDATE operation_items SET status = 'failed', error = ? WHERE id = ?",
                            ("Interrupted before the move could be confirmed; inspect both paths.", item_id),
                        )
                else:
                    undo_path = Path(row["undo_path"]) if row["undo_path"] else None
                    if undo_path and undo_path.exists() and not destination.exists():
                        connection.execute(
                            "UPDATE operation_items SET status = 'undone', error = NULL WHERE id = ?",
                            (item_id,),
                        )
                    elif destination.exists() and (not undo_path or not undo_path.exists()):
                        connection.execute(
                            "UPDATE operation_items SET status = 'moved', error = NULL WHERE id = ?",
                            (item_id,),
                        )
                    else:
                        connection.execute(
                            "UPDATE operation_items SET status = 'undo_failed', error = ? WHERE id = ?",
                            ("Interrupted during undo; inspect the recorded source, destination, and restore paths.", item_id),
                        )
            for operation_id in running_operations:
                connection.execute(
                    """UPDATE operations
                       SET status = CASE WHEN EXISTS (
                           SELECT 1 FROM operation_items WHERE operation_id = ? AND status = 'moved'
                       ) THEN 'partial' ELSE 'failed' END,
                       completed_at = ?, error = ? WHERE id = ? AND status = 'running'""",
                    (operation_id, datetime.now().astimezone().isoformat(), "Recovered an interrupted operation.", operation_id),
                )
            for operation_id in undoing_operations:
                item_states = connection.execute(
                    "SELECT status FROM operation_items WHERE operation_id = ?",
                    (operation_id,),
                ).fetchall()
                has_unrestored_moves = any(row["status"] in {"moved", "undoing", "undo_failed"} for row in item_states)
                recovered_status = "undo_partial" if has_unrestored_moves else "undone"
                connection.execute(
                    "UPDATE operations SET status = ?, completed_at = ?, error = ? WHERE id = ? AND status = 'undoing'",
                    (recovered_status, datetime.now().astimezone().isoformat(), "Recovered an interrupted undo.", operation_id),
                )
