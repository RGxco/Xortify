"""Create a deterministic, reviewable organization proposal."""

from __future__ import annotations

from pathlib import Path

from .bundles import fingerprint_records
from .intelligence import LocalPlacementAssistant
from .models import PlanItem, PlacementSuggestion, ScanResult


def _next_available(path: Path, reserved: set[str]) -> Path:
    candidate = path
    index = 2
    while candidate.exists() or str(candidate).casefold() in reserved:
        candidate = path.with_name(f"{path.stem} ({index}){path.suffix}")
        index += 1
    reserved.add(str(candidate).casefold())
    return candidate


def build_plan(
    scan: ScanResult,
    assistant: LocalPlacementAssistant | None = None,
) -> list[PlanItem]:
    """Propose reviewable moves while keeping recognized projects indivisible."""
    assistant = assistant or LocalPlacementAssistant()
    duplicate_hashes = {group[0].sha256 for group in scan.duplicate_groups}
    large_hashes = {record.sha256 for record in scan.large_files}
    root = scan.root.resolve()
    reserved: set[str] = set()
    items: list[PlanItem] = []
    project_roots = sorted(scan.project_directories, key=lambda path: str(path).casefold())

    for project in project_roots:
        if project.resolve(strict=False) == root:
            # The user-selected scan root is a protected container, not a move
            # candidate. Its project files are excluded from per-file plans.
            continue
        try:
            relative = project.relative_to(root)
        except ValueError:
            continue
        parts = relative.parts
        if len(parts) >= 2 and parts[0].casefold() == "code" and parts[1].casefold() == "projects":
            continue
        contained = [record for record in scan.files if project in record.path.parents]
        if not contained:
            continue
        destination_base = root / "Code" / "Projects" / project.name
        destination = _next_available(destination_base, reserved)
        items.append(
            PlanItem(
                source=project,
                destination=destination,
                relative_path=relative,
                category="Code",
                size=sum(record.size for record in contained),
                sha256=fingerprint_records(project, contained),
                is_duplicate=any(record.sha256 in duplicate_hashes for record in contained),
                is_large=any(record.sha256 in large_hashes for record in contained),
                ai_topic="Projects",
                ai_confidence=1.0,
                ai_reason="A project manifest or repository marker was found. The complete folder stays together.",
                ai_source="project",
                item_type="folder",
            )
        )

    for record in scan.files:
        source = record.path
        if any(project == source or project in source.parents for project in project_roots):
            continue
        parts = record.relative_path.parts
        already_in_category = bool(parts) and parts[0].casefold() == record.category.casefold()
        suggestion = (
            PlacementSuggestion(
                topic=record.visual_topic,
                confidence=record.visual_confidence,
                reason=f"The local image model recognized {record.visual_label or record.visual_topic}.",
                source="vision",
            )
            if record.category == "Images" and record.visual_topic
            else assistant.suggest(record)
        )
        topic = suggestion.topic if suggestion else None
        category_root = root / record.category
        if suggestion and suggestion.source == "vision":
            # Visually matched images from different source folders converge
            # into one topic collection; numbering prevents name collisions.
            destination_base = category_root / topic / source.name
        elif already_in_category:
            category_relative = Path(*parts[1:])
            already_in_topic = bool(topic and parts[1:2] and parts[1].casefold() == topic.casefold())
            destination_base = (
                category_root / topic / category_relative
                if topic and not already_in_topic
                else root / record.relative_path
            )
        elif topic and parts[0].casefold() != topic.casefold():
            destination_base = category_root / topic / record.relative_path
        else:
            destination_base = category_root / record.relative_path
        if source.resolve(strict=False) == destination_base.resolve(strict=False):
            continue
        destination = _next_available(destination_base, reserved)
        items.append(
            PlanItem(
                source=source,
                destination=destination,
                relative_path=record.relative_path,
                category=record.category,
                size=record.size,
                sha256=record.sha256,
                is_duplicate=record.sha256 in duplicate_hashes,
                is_large=record.sha256 in large_hashes,
                ai_topic=topic,
                ai_confidence=suggestion.confidence if suggestion else 0.0,
                ai_reason=suggestion.reason if suggestion else "No clear name or folder cue; keeping the category suggestion.",
                ai_source=suggestion.source if suggestion else "none",
            )
        )
    return items
