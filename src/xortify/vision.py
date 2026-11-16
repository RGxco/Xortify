"""Optional offline image recognition using a small quantized ONNX model."""

from __future__ import annotations

import hashlib
import importlib.util
import os
import re
import urllib.request
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path
from typing import Callable, Iterable

from .models import FileRecord

MODEL_URL = (
    "https://huggingface.co/ketiswp/"
    "mediapipe-EfficientNet-Lite0-ImageNet-224-int8-uint8-onnx/resolve/main/model.onnx"
)
MODEL_SHA256 = "bd61897fc7744478bd42bb7714ed22769cc0bf05a0980c9ce03dcf48cace26bc"
MODEL_SIZE_BYTES = 5_148_096
MODEL_FILENAME = "efficientnet_lite0_imagenet_int8.onnx"
MIN_IMAGE_CONFIDENCE = 0.10

ProgressCallback = Callable[[int, int], None]


def model_directory() -> Path:
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return base / "Xortify" / "models"


def model_path() -> Path:
    return model_directory() / MODEL_FILENAME


def vision_runtime_available() -> bool:
    return all(importlib.util.find_spec(name) is not None for name in ("numpy", "onnxruntime", "PIL"))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def image_model_installed() -> bool:
    path = model_path()
    try:
        return path.is_file() and path.stat().st_size == MODEL_SIZE_BYTES and _sha256(path) == MODEL_SHA256
    except OSError:
        return False


def download_image_model(progress_callback: ProgressCallback | None = None) -> Path:
    """Download and verify the fixed model weights; no personal file is sent."""
    target = model_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    if image_model_installed():
        return target
    partial = target.with_suffix(target.suffix + ".part")
    digest = hashlib.sha256()
    downloaded = 0
    try:
        request = urllib.request.Request(
            MODEL_URL,
            headers={"User-Agent": "Xortify/0.1 local-model-installer"},
        )
        with urllib.request.urlopen(request, timeout=30) as response, partial.open("wb") as output:
            total = int(response.headers.get("Content-Length") or MODEL_SIZE_BYTES)
            while True:
                block = response.read(256 * 1024)
                if not block:
                    break
                output.write(block)
                digest.update(block)
                downloaded += len(block)
                if progress_callback:
                    progress_callback(downloaded, total)
        if downloaded != MODEL_SIZE_BYTES or digest.hexdigest() != MODEL_SHA256:
            raise OSError("The downloaded image model failed its size or SHA-256 integrity check.")
        os.replace(partial, target)
        return target
    except Exception:
        partial.unlink(missing_ok=True)
        raise


@dataclass(frozen=True, slots=True)
class ImagePrediction:
    label: str
    topic: str | None
    confidence: float
    class_index: int


def _labels() -> list[str]:
    text = files("xortify").joinpath("assets", "imagenet_labels.txt").read_text(encoding="utf-8")
    labels = [line.strip() for line in text.splitlines() if line.strip()]
    # MediaPipe's public label map has a leading background label. The model
    # returns 1,000 ImageNet classes, which start at the following line.
    if labels and labels[0].casefold() == "background":
        labels = labels[1:]
    return labels


_FOOD_WORDS = {
    "bagel", "banana", "biscuit", "bread", "broccoli", "burrito", "cake", "candy",
    "carrot", "cheeseburger", "chocolate", "coffee", "cookie", "corn", "dessert",
    "donut", "dough", "food", "fruit", "guacamole", "hamburger", "hot dog", "ice cream",
    "lemon", "lime", "meat", "mushroom", "orange", "pasta", "pizza", "pretzel", "salad",
    "sandwich", "soup", "strawberry", "sushi", "taco", "tomato", "vegetable", "waffle",
}
_VEHICLE_WORDS = {
    "aircraft", "airliner", "ambulance", "bicycle", "boat", "bus", "car", "convertible",
    "fire engine", "jeep", "limousine", "locomotive", "motorcycle", "railcar", "ship",
    "scooter", "taxi", "tractor", "train", "truck", "van",
}
_NATURE_WORDS = {
    "alp", "beach", "cliff", "cloud", "coral reef", "desert", "field", "flower", "forest",
    "garden", "glacier", "grass", "hill", "island", "lake", "landscape", "mountain", "ocean",
    "plant", "rainforest", "river", "sea", "shore", "sky", "tree", "valley", "volcano", "waterfall",
}
_SPORT_WORDS = {
    "ball", "baseball", "basketball", "bobsled", "golf", "hockey", "racket", "rugby", "skateboard",
    "ski", "snowboard", "soccer", "surfboard", "tennis", "volleyball",
}


def topic_for_class(class_index: int, label: str) -> str | None:
    """Map detailed ImageNet labels into useful, stable album folders."""
    if 281 <= class_index <= 285:
        return "Cats"
    if 151 <= class_index <= 268:
        return "Dogs"
    if (7 <= class_index <= 24) or (80 <= class_index <= 146):
        return "Birds"
    if 0 <= class_index <= 397:
        return "Animals"

    normalized = label.casefold()
    words = set(normalized.replace("-", " ").split())
    if _contains_term(normalized, _FOOD_WORDS):
        return "Food"
    if _contains_term(normalized, _VEHICLE_WORDS):
        return "Vehicles"
    if _contains_term(normalized, _NATURE_WORDS):
        return "Nature"
    if _contains_term(normalized, _SPORT_WORDS):
        return "Sports"
    if words & {"screen", "web", "website", "desktop"}:
        return "Screenshots"
    return None


def _contains_term(label: str, terms: set[str]) -> bool:
    normalized = label.replace("-", " ")
    return any(re.search(rf"\b{re.escape(term)}\b", normalized) for term in terms)


class LocalImageClassifier:
    """CPU-only ONNX Runtime wrapper with one-image-at-a-time memory use."""

    def __init__(self, path: Path | str | None = None):
        try:
            import numpy as np
            import onnxruntime as ort
            from PIL import Image, ImageOps
        except ImportError as error:
            raise RuntimeError(
                "Install Xortify's image AI dependencies with: python -m pip install -e .[vision]"
            ) from error

        self.np = np
        self.Image = Image
        self.ImageOps = ImageOps
        options = ort.SessionOptions()
        options.intra_op_num_threads = 1
        options.inter_op_num_threads = 1
        options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
        options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        self.session = ort.InferenceSession(
            str(path or model_path()), sess_options=options, providers=["CPUExecutionProvider"]
        )
        self.input = self.session.get_inputs()[0]
        self.labels = _labels()
        if len(self.labels) != 1000:
            raise RuntimeError(f"Expected 1,000 image labels, found {len(self.labels)}.")

    def predict(self, image_path: Path | str) -> ImagePrediction:
        with self.Image.open(image_path) as image:
            oriented = self.ImageOps.exif_transpose(image).convert("RGB")
            resized = self.ImageOps.fit(
                oriented,
                (224, 224),
                method=self.Image.Resampling.BILINEAR,
                centering=(0.5, 0.5),
            )
            tensor = self.np.expand_dims(self.np.asarray(resized, dtype=self.np.uint8), axis=0)
        raw = self.session.run(None, {self.input.name: tensor})[0].reshape(-1)
        if raw.size != len(self.labels):
            raise RuntimeError(f"Unexpected image model output with {raw.size} classes.")
        class_index = int(raw.argmax())
        value = float(raw[class_index])
        confidence = value / 255.0 if raw.dtype == self.np.uint8 else value
        label = self.labels[class_index]
        topic = topic_for_class(class_index, label) if confidence >= MIN_IMAGE_CONFIDENCE else None
        return ImagePrediction(label, topic, confidence, class_index)


def analyze_image_files(
    records: Iterable[FileRecord],
    project_directories: Iterable[Path],
    *,
    progress_callback: Callable[[int, int, Path], None] | None = None,
) -> int:
    """Annotate eligible image records locally. Returns successful predictions."""
    projects = tuple(Path(path) for path in project_directories)
    images = [
        record
        for record in records
        if record.category == "Images"
        and not any(project == record.path or project in record.path.parents for project in projects)
    ]
    if not images:
        return 0
    if not image_model_installed():
        return 0
    classifier = LocalImageClassifier()
    done = 0
    for index, record in enumerate(images, start=1):
        try:
            prediction = classifier.predict(record.path)
            record.visual_label = prediction.label
            record.visual_topic = prediction.topic
            record.visual_confidence = prediction.confidence
            done += 1
        except Exception:
            # The deterministic scan remains usable when one image is corrupt,
            # unsupported, or briefly locked by another application.
            pass
        if progress_callback:
            progress_callback(index, len(images), record.path)
    return done
