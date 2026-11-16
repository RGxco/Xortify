"""Recognize project folders and fingerprint them as indivisible move units."""

from __future__ import annotations

import hashlib
import os
import stat as stat_module
from pathlib import Path
from typing import Iterable

from .models import FileRecord

_FILE_MARKERS: tuple[tuple[str, str], ...] = (
    ("pyproject.toml", "Python project"),
    ("package.json", "Node project"),
    ("cargo.toml", "Rust project"),
    ("go.mod", "Go project"),
    ("pom.xml", "Java project"),
    ("build.gradle", "Gradle project"),
    ("build.gradle.kts", "Gradle project"),
    ("composer.json", "PHP project"),
    ("cmakelists.txt", "C/C++ project"),
    ("meson.build", "C/C++ project"),
    ("setup.py", "Python project"),
    ("setup.cfg", "Python project"),
)


def project_marker(filenames: Iterable[str], dirnames: Iterable[str]) -> str | None:
    """Return a short explanation for common project/repository markers.

    A generic requirements.txt file is intentionally not enough on its own;
    it is common in folders that are not complete Python projects.
    """
    files = {name.casefold() for name in filenames}
    directories = {name.casefold() for name in dirnames}
    for name, description in _FILE_MARKERS:
        if name in files:
            return description
    if any(name.endswith((".sln", ".csproj", ".vbproj", ".fsproj")) for name in files):
        return ".NET project"
    if any(name.endswith(".xcodeproj") for name in directories):
        return "Xcode project"
    if any(name.endswith(".uproject") for name in files):
        return "Unreal project"
    if ".git" in directories:
        return "Git repository"
    return None


def fingerprint_records(directory: Path, records: Iterable[FileRecord]) -> str:
    """Hash sorted relative paths and scanned file hashes for a project tree."""
    directory = directory.resolve(strict=False)
    entries: list[tuple[str, str]] = []
    for record in records:
        try:
            relative = record.path.relative_to(directory).as_posix()
        except ValueError:
            continue
        entries.append((relative, record.sha256))
    digest = hashlib.sha256()
    for relative, file_hash in sorted(entries, key=lambda item: item[0].casefold()):
        digest.update(b"F\0")
        digest.update(relative.encode("utf-8", "surrogatepass"))
        digest.update(b"\0")
        digest.update(file_hash.encode("ascii"))
        digest.update(b"\0")
    return digest.hexdigest()


def _is_link_or_reparse(path: Path) -> bool:
    if path.is_symlink():
        return True
    try:
        attributes = getattr(path.lstat(), "st_file_attributes", 0)
        return bool(attributes & getattr(stat_module, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))
    except OSError:
        return True


def fingerprint_directory(directory: Path) -> str:
    """Hash current regular-file paths and contents without following links."""
    entries: list[tuple[str, str]] = []

    def on_error(error: OSError) -> None:
        raise error

    for current_text, dirnames, filenames in os.walk(
        directory, topdown=True, followlinks=False, onerror=on_error
    ):
        current = Path(current_text)
        dirnames[:] = sorted(
            (name for name in dirnames if not _is_link_or_reparse(current / name)),
            key=str.casefold,
        )
        for filename in sorted(filenames, key=str.casefold):
            path = current / filename
            if _is_link_or_reparse(path) or not path.is_file():
                continue
            relative = path.relative_to(directory).as_posix()
            file_digest = hashlib.sha256()
            with path.open("rb") as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b""):
                    file_digest.update(block)
            entries.append((relative, file_digest.hexdigest()))

    digest = hashlib.sha256()
    for relative, file_hash in sorted(entries, key=lambda item: item[0].casefold()):
            digest.update(b"F\0")
            digest.update(relative.encode("utf-8", "surrogatepass"))
            digest.update(b"\0")
            digest.update(file_hash.encode("ascii"))
            digest.update(b"\0")
    return digest.hexdigest()
