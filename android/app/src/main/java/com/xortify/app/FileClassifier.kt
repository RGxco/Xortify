package com.xortify.app

import android.webkit.MimeTypeMap
import java.util.Locale

private val extensionCategories = mapOf(
    "png" to "Images", "jpg" to "Images", "jpeg" to "Images", "gif" to "Images", "webp" to "Images",
    "bmp" to "Images", "tif" to "Images", "tiff" to "Images", "heic" to "Images", "heif" to "Images",
    "avif" to "Images", "svg" to "Images", "ico" to "Images", "raw" to "Images", "cr2" to "Images",
    "nef" to "Images", "arw" to "Images", "mp4" to "Videos", "m4v" to "Videos", "mov" to "Videos",
    "mkv" to "Videos", "avi" to "Videos", "webm" to "Videos", "mpeg" to "Videos", "mpg" to "Videos",
    "wmv" to "Videos", "flv" to "Videos", "3gp" to "Videos", "mts" to "Videos", "m2ts" to "Videos",
    "pdf" to "Documents", "doc" to "Documents", "docx" to "Documents", "odt" to "Documents",
    "rtf" to "Documents", "txt" to "Documents", "md" to "Documents", "csv" to "Documents",
    "tsv" to "Documents", "xls" to "Documents", "xlsx" to "Documents", "ods" to "Documents",
    "ppt" to "Documents", "pptx" to "Documents", "odp" to "Documents", "epub" to "Documents",
    "xml" to "Documents", "json" to "Documents", "yaml" to "Documents", "yml" to "Documents",
    "mp3" to "Audio", "wav" to "Audio", "flac" to "Audio", "aac" to "Audio", "m4a" to "Audio",
    "ogg" to "Audio", "opus" to "Audio", "wma" to "Audio", "aiff" to "Audio", "mid" to "Audio",
    "zip" to "Archives", "rar" to "Archives", "7z" to "Archives", "tar" to "Archives", "gz" to "Archives",
    "bz2" to "Archives", "xz" to "Archives", "zst" to "Archives", "cab" to "Archives", "iso" to "Archives",
    "py" to "Code", "js" to "Code", "jsx" to "Code", "ts" to "Code", "tsx" to "Code", "html" to "Code",
    "css" to "Code", "java" to "Code", "kt" to "Code", "kts" to "Code", "c" to "Code", "cpp" to "Code",
    "h" to "Code", "cs" to "Code", "go" to "Code", "rs" to "Code", "swift" to "Code", "rb" to "Code",
    "php" to "Code", "sh" to "Code", "ps1" to "Code", "sql" to "Code", "toml" to "Code", "ini" to "Code",
    "gradle" to "Code", "dart" to "Code", "vue" to "Code", "svelte" to "Code", "dockerfile" to "Code",
    "exe" to "Installers", "msi" to "Installers", "apk" to "Installers", "aab" to "Installers",
)

fun classify(name: String, header: ByteArray, mimeType: String?): String {
    val ext = name.substringAfterLast('.', "").lowercase(Locale.ROOT)
    if (ext in setOf("docx", "docm", "xlsx", "xlsm", "pptx", "pptm", "odt", "ods", "odp", "epub")) return "Documents"
    val signature = when {
        header.hasPrefix(byteArrayOf(0x89.toByte(), 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a)) -> "Images"
        header.hasPrefix(byteArrayOf(0xff.toByte(), 0xd8.toByte(), 0xff.toByte())) -> "Images"
        header.hasPrefix("GIF87a".encodeToByteArray()) || header.hasPrefix("GIF89a".encodeToByteArray()) -> "Images"
        header.hasPrefix("BM".encodeToByteArray()) -> "Images"
        header.hasPrefix("RIFF".encodeToByteArray()) && header.size >= 12 && String(header, 8, 4) == "WEBP" -> "Images"
        header.size >= 12 && String(header, 4, 4) == "ftyp" -> "Videos"
        header.hasPrefix(byteArrayOf(0x1a, 0x45, 0xdf.toByte(), 0xa3.toByte())) -> "Videos"
        header.hasPrefix("ID3".encodeToByteArray()) || (header.size > 1 && header[0] == 0xff.toByte() && (header[1].toInt() and 0xe0) == 0xe0) -> "Audio"
        header.hasPrefix("fLaC".encodeToByteArray()) || header.hasPrefix("OggS".encodeToByteArray()) -> "Audio"
        header.hasPrefix("%PDF-".encodeToByteArray()) -> "Documents"
        header.hasPrefix(byteArrayOf(0x50, 0x4b, 0x03, 0x04)) || header.hasPrefix("Rar!".encodeToByteArray()) -> "Archives"
        header.hasPrefix(byteArrayOf(0x37, 0x7a, 0xbc.toByte(), 0xaf.toByte(), 0x27, 0x1c)) -> "Archives"
        header.hasPrefix(byteArrayOf(0x1f, 0x8b.toByte())) -> "Archives"
        header.hasPrefix("MZ".encodeToByteArray()) -> "Installers"
        else -> null
    }
    if (signature != null) return signature
    extensionCategories[ext]?.let { return it }
    return when {
        mimeType?.startsWith("image/") == true -> "Images"
        mimeType?.startsWith("video/") == true -> "Videos"
        mimeType?.startsWith("audio/") == true -> "Audio"
        mimeType == "application/pdf" || mimeType?.startsWith("text/") == true -> "Documents"
        else -> MimeTypeMap.getSingleton().getMimeTypeFromExtension(ext)?.let { type ->
            when {
                type.startsWith("image/") -> "Images"
                type.startsWith("video/") -> "Videos"
                type.startsWith("audio/") -> "Audio"
                type.startsWith("text/") -> "Documents"
                else -> "Other"
            }
        } ?: "Other"
    }
}

private fun ByteArray.hasPrefix(prefix: ByteArray): Boolean =
    size >= prefix.size && prefix.indices.all { this[it] == prefix[it] }

fun isProjectMarker(fileNames: Set<String>, directoryNames: Set<String>): Boolean {
    val files = fileNames.map { it.lowercase(Locale.ROOT) }.toSet()
    val dirs = directoryNames.map { it.lowercase(Locale.ROOT) }.toSet()
    return files.any { it in setOf(
        "pyproject.toml", "package.json", "cargo.toml", "go.mod", "pom.xml", "build.gradle",
        "build.gradle.kts", "composer.json", "cmakelists.txt", "meson.build", "setup.py", "setup.cfg",
        "pubspec.yaml", "deno.json", "deno.jsonc", "gemfile", "mix.exs", "*.sln",
    ) || it.endsWith(".sln") || it.endsWith(".csproj") || it.endsWith(".vbproj") || it.endsWith(".fsproj") || it.endsWith(".uproject") } ||
        dirs.any { it in setOf(".git", ".xcodeproj") || it.endsWith(".xcodeproj") }
}

fun mimeFor(name: String): String = MimeTypeMap.getSingleton()
    .getMimeTypeFromExtension(name.substringAfterLast('.', "").lowercase(Locale.ROOT)) ?: "application/octet-stream"
