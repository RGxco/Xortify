"""Conservative local file classification using signatures and file metadata."""

from __future__ import annotations

import mimetypes
from pathlib import Path

CATEGORIES = (
    "Images",
    "Videos",
    "Documents",
    "Audio",
    "Archives",
    "Code",
    "Installers",
    "Other",
)

_EXTENSION_CATEGORIES: dict[str, str] = {}


def _register(category: str, extensions: str) -> None:
    for extension in extensions.split():
        _EXTENSION_CATEGORIES[extension] = category


_register("Images", ".png .jpg .jpeg .gif .webp .bmp .tif .tiff .heic .heif .avif .svg .ico .raw .cr2 .nef .arw")
_register("Videos", ".mp4 .m4v .mov .mkv .avi .webm .mpeg .mpg .m2v .wmv .flv .3gp .mts .m2ts .ogv")
_register("Documents", ".pdf .doc .docx .docm .odt .rtf .txt .md .csv .tsv .xls .xlsx .xlsm .ods .ppt .pptx .pptm .odp .epub .pages .numbers .key .xml .json .yaml .yml")
_register("Audio", ".mp3 .wav .flac .aac .m4a .ogg .opus .wma .aiff .aif .mid .midi .amr .weba")
_register("Archives", ".zip .rar .7z .tar .gz .bz2 .xz .zst .cab .iso .dmg .tgz .tbz2 .txz")
_register("Code", ".py .pyw .js .jsx .ts .tsx .html .htm .css .scss .java .kt .kts .c .h .cc .cpp .hpp .cs .go .rs .swift .rb .php .sh .bash .ps1 .bat .cmd .sql .toml .ini .cfg .conf .env .ipynb .vue .svelte .dart .lua .r .m .mm .ex .exs .erl .hrl .hs .lhs .pl .pm .clj .cljs .scala .gradle .tf .dockerfile .makefile")
_register("Installers", ".exe .msi .msix .appx .msu .apk .deb .rpm .pkg .appinstaller")

_IMAGE_SIGNATURES: tuple[tuple[bytes, str], ...] = (
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"GIF87a", "image/gif"),
    (b"GIF89a", "image/gif"),
    (b"BM", "image/bmp"),
    (b"II*\x00", "image/tiff"),
    (b"MM\x00*", "image/tiff"),
    (b"RIFF", "image/webp"),
)


def _mime_category(mime_type: str | None) -> str | None:
    if not mime_type:
        return None
    main_type = mime_type.split(";", 1)[0].lower()
    if main_type.startswith("image/"):
        return "Images"
    if main_type.startswith("video/"):
        return "Videos"
    if main_type.startswith("audio/"):
        return "Audio"
    if main_type in {"application/pdf", "application/rtf"} or main_type.startswith("text/"):
        return "Documents"
    return None


def classify_header(header: bytes, extension: str = "") -> tuple[str | None, str | None]:
    """Return (category, detected MIME) for recognizable file signatures."""
    ext = extension.lower()

    # Office and e-book formats may be ZIP containers; their known extensions
    # are more useful than the generic archive signature.
    if ext in {".docx", ".docm", ".xlsx", ".xlsm", ".pptx", ".pptm", ".odt", ".ods", ".odp", ".epub"}:
        return "Documents", mimetypes.guess_type("file" + ext)[0]

    for signature, mime in _IMAGE_SIGNATURES:
        if header.startswith(signature):
            if signature == b"RIFF" and header[8:12] != b"WEBP":
                continue
            return "Images", mime
    if len(header) >= 12 and header[4:8] == b"ftyp":
        return "Videos", "video/mp4"
    if header.startswith(b"\x1a\x45\xdf\xa3"):
        return "Videos", "video/x-matroska"
    if header.startswith(b"RIFF") and header[8:12] == b"AVI ":
        return "Videos", "video/x-msvideo"
    if header.startswith((b"\x00\x00\x01\xba", b"\x00\x00\x01\xb3")):
        return "Videos", "video/mpeg"

    if header.startswith(b"ID3") or header.startswith((b"\xff\xfb", b"\xff\xf3", b"\xff\xf2")):
        return "Audio", "audio/mpeg"
    if header.startswith(b"fLaC"):
        return "Audio", "audio/flac"
    if header.startswith(b"OggS"):
        return "Audio", "audio/ogg"
    if header.startswith(b"RIFF") and header[8:12] == b"WAVE":
        return "Audio", "audio/wav"
    if header.startswith(b"FORM") and header[8:12] in {b"AIFF", b"AIFC"}:
        return "Audio", "audio/aiff"

    if header.startswith(b"%PDF-"):
        return "Documents", "application/pdf"
    if header.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"):
        return "Documents", "application/x-ole-storage"
    if header.startswith((b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08")):
        return "Archives", "application/zip"
    if header.startswith(b"Rar!\x1a\x07"):
        return "Archives", "application/vnd.rar"
    if header.startswith(b"7z\xbc\xaf\x27\x1c"):
        return "Archives", "application/x-7z-compressed"
    if header.startswith(b"\x1f\x8b"):
        return "Archives", "application/gzip"
    if header.startswith(b"BZh"):
        return "Archives", "application/x-bzip2"
    if header.startswith(b"\xfd7zXZ\x00"):
        return "Archives", "application/x-xz"
    if len(header) >= 262 and header[257:262] == b"ustar":
        return "Archives", "application/x-tar"
    if header.startswith(b"MZ"):
        return "Installers", "application/vnd.microsoft.portable-executable"

    return None, None


def classify_file(path: Path, header: bytes | None = None) -> tuple[str, str | None]:
    """Classify one path from its header, extension, and Python MIME metadata."""
    extension = path.suffix.lower()
    if header is None:
        try:
            with path.open("rb") as stream:
                header = stream.read(8192)
        except OSError:
            header = b""

    detected_category, detected_mime = classify_header(header, extension)
    if detected_category:
        return detected_category, detected_mime or mimetypes.guess_type(path.name)[0]

    extension_category = _EXTENSION_CATEGORIES.get(extension)
    if extension_category:
        return extension_category, mimetypes.guess_type(path.name)[0]

    mime_type = mimetypes.guess_type(path.name)[0]
    return _mime_category(mime_type) or "Other", mime_type
