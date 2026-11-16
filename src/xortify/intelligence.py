"""Tiny offline placement assistant using name cues and approved examples.

This deliberately avoids model downloads and content extraction. It uses a
small topic cue list and a nearest-example similarity lookup over local names
and folder paths, so the model stays private, explainable, and inexpensive.
"""

from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path

from .models import FileRecord, PlacementSuggestion

_STOP_WORDS = {
    "a", "an", "and", "are", "copy", "file", "final", "for", "from", "img",
    "new", "of", "old", "scan", "the", "to", "untitled", "version",
}
_TOKEN_PATTERN = re.compile(r"[a-z]{2,}")

# topic, eligible deterministic categories, matching filename/folder words
_TOPIC_CUES: tuple[tuple[str, frozenset[str], frozenset[str]], ...] = (
    ("Receipts", frozenset({"Documents", "Images"}), frozenset({"receipt", "invoice", "bill", "statement", "tax", "transaction", "expense", "reimbursement"})),
    ("Travel", frozenset({"Documents", "Images", "Videos"}), frozenset({"travel", "trip", "vacation", "holiday", "itinerary", "flight", "boarding", "hotel", "passport", "booking"})),
    ("Work", frozenset({"Documents", "Code", "Archives"}), frozenset({"work", "client", "contract", "proposal", "meeting", "agenda", "presentation", "timesheet", "resume", "cv"})),
    ("Learning", frozenset({"Documents", "Audio"}), frozenset({"course", "class", "lecture", "lesson", "homework", "assignment", "syllabus", "textbook", "exam", "study"})),
    ("Screenshots", frozenset({"Images"}), frozenset({"screenshot", "screenshots", "snip", "snipping", "capture"})),
    ("Design", frozenset({"Images", "Documents", "Code"}), frozenset({"design", "mockup", "wireframe", "prototype", "logo", "brand", "sketch", "figma", "ui", "ux"})),
    ("Family", frozenset({"Images", "Videos", "Documents"}), frozenset({"family", "wedding", "birthday", "reunion", "party", "anniversary"})),
    ("Podcasts", frozenset({"Audio"}), frozenset({"podcast", "episode", "interview"})),
    ("Voice Notes", frozenset({"Audio"}), frozenset({"voice", "recording", "memo", "dictation"})),
    ("Music", frozenset({"Audio"}), frozenset({"music", "song", "album", "artist", "playlist", "track"})),
    ("Screen Recordings", frozenset({"Videos"}), frozenset({"screen", "recording", "capture", "screencast"})),
    ("Movies", frozenset({"Videos"}), frozenset({"movie", "film", "trailer", "cinema"})),
    ("Projects", frozenset({"Code", "Archives", "Documents"}), frozenset({"project", "repository", "repo", "source", "build", "release"})),
)


def _tokens(value: str) -> set[str]:
    normalized = value.replace("_", " ").replace("-", " ").casefold()
    return {token for token in _TOKEN_PATTERN.findall(normalized) if token not in _STOP_WORDS}


def placement_features(category: str, file_name: str, relative_path: Path) -> list[str]:
    """Build small, non-content features for private local learning."""
    features = {f"name:{token}" for token in _tokens(Path(file_name).stem)}
    for part in relative_path.parent.parts:
        if part.casefold() != category.casefold():
            features.update(f"folder:{token}" for token in _tokens(part))
    extension = Path(file_name).suffix.casefold().lstrip(".")
    if extension:
        features.add(f"extension:{extension}")
    features.add(f"category:{category.casefold()}")
    return sorted(features)


def _meaningful_tokens(features: set[str]) -> set[str]:
    return {
        feature.split(":", 1)[1]
        for feature in features
        if feature.startswith(("name:", "folder:"))
    }


def _rule_suggestion(record: FileRecord) -> PlacementSuggestion | None:
    name_tokens = _tokens(record.path.stem)
    folder_tokens: set[str] = set()
    for part in record.relative_path.parent.parts:
        if part.casefold() != record.category.casefold():
            folder_tokens.update(_tokens(part))

    candidates: list[tuple[float, PlacementSuggestion]] = []
    for topic, categories, cues in _TOPIC_CUES:
        if record.category not in categories:
            continue
        name_hits = sorted(name_tokens & cues)
        folder_hits = sorted(folder_tokens & cues)
        if not name_hits and not folder_hits:
            continue
        score = len(name_hits) * 1.0 + len(folder_hits) * 0.78
        confidence = min(0.93, 0.65 + score * 0.11)
        if name_hits and folder_hits:
            reason = f"Name and folder cues: {', '.join(name_hits[:2] + folder_hits[:2])}."
        elif name_hits:
            reason = f"Filename cue: {', '.join(name_hits[:3])}."
        else:
            reason = f"Folder cue: {', '.join(folder_hits[:3])}."
        candidates.append((score, PlacementSuggestion(topic, confidence, reason, "rule")))
    return max(candidates, key=lambda item: item[0])[1] if candidates else None


class LocalPlacementAssistant:
    """Suggest topical subfolders from local cues and approved placements."""

    def __init__(self, examples: list[dict[str, object]] | None = None):
        self.examples = examples or []

    def _learned_suggestion(self, record: FileRecord) -> PlacementSuggestion | None:
        query = _meaningful_tokens(set(placement_features(record.category, record.path.name, record.relative_path)))
        if not query:
            return None
        votes: dict[str, float] = defaultdict(float)
        support: dict[str, int] = defaultdict(int)
        best_similarity = 0.0
        for example in self.examples:
            if str(example.get("category", "")).casefold() != record.category.casefold():
                continue
            topic = str(example.get("topic", "")).strip()
            known = _meaningful_tokens(set(str(example.get("features", "")).split()))
            if not topic or not known:
                continue
            intersection = query & known
            if not intersection:
                continue
            similarity = len(intersection) / len(query | known)
            if similarity < 0.18:
                continue
            votes[topic] += similarity * similarity
            support[topic] += 1
            best_similarity = max(best_similarity, similarity)
        if not votes:
            return None

        topic, score = max(votes.items(), key=lambda item: item[1])
        total = sum(votes.values())
        agreement = score / total if total else 0.0
        confidence = min(0.94, 0.55 + 0.35 * best_similarity + 0.08 * agreement + 0.02 * max(0, support[topic] - 1))
        if confidence < 0.68:
            return None
        count = support[topic]
        suffix = "placement" if count == 1 else "placements"
        reason = f"Similar to {count} approved {topic} {suffix}."
        return PlacementSuggestion(topic, confidence, reason, "learned")

    def suggest(self, record: FileRecord) -> PlacementSuggestion | None:
        rule = _rule_suggestion(record)
        learned = self._learned_suggestion(record)
        if learned and (rule is None or learned.confidence >= rule.confidence + 0.04):
            return learned
        return rule or learned


def topic_from_destination(root: Path, item) -> str | None:
    """Extract a chosen topic folder from a destination inside the scan root."""
    try:
        destination_parts = Path(item.destination).resolve(strict=False).relative_to(root.resolve()).parts
    except (OSError, ValueError):
        return None
    if not destination_parts:
        return None
    has_category_root = destination_parts[0].casefold() == item.category.casefold()
    destination_tail = destination_parts[1:] if has_category_root else destination_parts
    if len(destination_tail) < 2:
        return None
    source_parts = Path(item.relative_path).parts
    suffix_length = 0
    for offset in range(1, min(len(destination_tail), len(source_parts)) + 1):
        if destination_tail[-offset].casefold() != source_parts[-offset].casefold():
            break
        suffix_length = offset
    inserted_parts = destination_tail[:-suffix_length] if suffix_length else destination_tail[:-1]
    if not inserted_parts:
        return None
    topic = inserted_parts[0].strip()
    if not topic or topic.casefold() in {".", "..", item.category.casefold()}:
        return None
    return topic
