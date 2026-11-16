"""Data structures shared by scanning, planning, storage, and the UI."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


@dataclass(slots=True)
class FileRecord:
    path: Path
    relative_path: Path
    size: int
    modified_at: datetime
    category: str
    mime_type: str | None
    sha256: str
    visual_label: str | None = None
    visual_topic: str | None = None
    visual_confidence: float = 0.0


@dataclass(slots=True)
class ScanResult:
    root: Path
    files: list[FileRecord] = field(default_factory=list)
    empty_directories: list[Path] = field(default_factory=list)
    duplicate_groups: list[list[FileRecord]] = field(default_factory=list)
    large_files: list[FileRecord] = field(default_factory=list)
    unreadable_files: list[tuple[Path, str]] = field(default_factory=list)
    project_directories: list[Path] = field(default_factory=list)
    started_at: datetime | None = None
    finished_at: datetime | None = None

    @property
    def duplicate_file_count(self) -> int:
        return sum(len(group) for group in self.duplicate_groups)


@dataclass(slots=True)
class PlanItem:
    source: Path
    destination: Path
    relative_path: Path
    category: str
    size: int
    sha256: str
    is_duplicate: bool = False
    is_large: bool = False
    selected: bool = True
    ai_topic: str | None = None
    ai_confidence: float = 0.0
    ai_reason: str = ""
    ai_source: str = "none"
    item_type: str = "file"


@dataclass(slots=True)
class PlacementSuggestion:
    topic: str
    confidence: float
    reason: str
    source: str


@dataclass(slots=True)
class OperationResult:
    operation_id: int
    moved: int
    failed: list[tuple[Path, str]] = field(default_factory=list)
    learned: int = 0


@dataclass(slots=True)
class UndoResult:
    operation_id: int
    restored: int
    failed: list[tuple[Path, str]] = field(default_factory=list)
