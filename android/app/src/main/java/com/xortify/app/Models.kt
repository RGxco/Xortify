package com.xortify.app

import android.net.Uri

data class PlannedMove(
    val id: String,
    val uri: Uri,
    val parentUri: Uri,
    val name: String,
    val relativePath: String,
    val category: String,
    val destination: String,
    val size: Long,
    val sha256: String,
    val isDirectory: Boolean = false,
    val visualLabel: String? = null,
    val selected: Boolean = true,
    val moved: Boolean = false,
    val detail: String = "",
)

data class DuplicateGroup(val sha256: String, val locations: List<String>, val size: Long)

data class ScanReport(
    val moves: List<PlannedMove>,
    val fileCount: Int,
    val emptyFolders: List<String>,
    val largeFiles: List<Pair<String, Long>>,
    val duplicates: List<DuplicateGroup>,
    val errors: Int,
    val notes: List<String> = emptyList(),
)

data class MoveBatchResult(val movedIds: Set<String>, val errors: List<String>)

enum class AppPage(val label: String, val symbol: String) {
    Review("Review plan", "▤"),
    Findings("Findings", "✦"),
    Activity("Activity", "◴"),
}

data class XortifyState(
    val treeUri: Uri? = null,
    val folderLabel: String = "Choose a folder to explore",
    val moves: List<PlannedMove> = emptyList(),
    val fileCount: Int = 0,
    val emptyFolders: List<String> = emptyList(),
    val largeFiles: List<Pair<String, Long>> = emptyList(),
    val duplicates: List<DuplicateGroup> = emptyList(),
    val activity: List<String> = emptyList(),
    val page: AppPage = AppPage.Review,
    val busy: Boolean = false,
    val modelInstalled: Boolean = false,
    val status: String = "Select a local folder. Scanning is read-only.",
    val error: String? = null,
) {
    val selectedCount: Int get() = moves.count { it.selected && !it.moved }
    val duplicateCount: Int get() = duplicates.sumOf { (it.locations.size - 1).coerceAtLeast(0) }
    val largeCount: Int get() = largeFiles.size
    val emptyCount: Int get() = emptyFolders.size
}

fun formatBytes(bytes: Long): String = when {
    bytes >= 1024L * 1024 * 1024 -> "%.1f GB".format(bytes / (1024.0 * 1024 * 1024))
    bytes >= 1024L * 1024 -> "%.1f MB".format(bytes / (1024.0 * 1024))
    bytes >= 1024 -> "%.1f KB".format(bytes / 1024.0)
    else -> "$bytes B"
}
