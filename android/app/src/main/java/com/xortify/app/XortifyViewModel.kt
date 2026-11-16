package com.xortify.app

import android.app.Application
import android.content.Intent
import android.net.Uri
import android.os.Handler
import android.os.Looper
import androidx.documentfile.provider.DocumentFile
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

class XortifyViewModel(application: Application) : AndroidViewModel(application) {
    private val journal = MoveJournal(application)
    private val organizer = SafOrganizer(application, journal)
    private val mainHandler = Handler(Looper.getMainLooper())
    val state = androidx.compose.runtime.mutableStateOf(initialState(application))

    init { refreshActivity() }

    fun selectTree(uri: Uri) {
        if (uri.authority != "com.android.externalstorage.documents") {
            state.value = state.value.copy(
                status = "Xortify works with folders in phone storage or an SD card, keeping the scan local.",
                error = null,
            )
            return
        }
        try {
            getApplication<Application>().contentResolver.takePersistableUriPermission(
                uri, Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_GRANT_WRITE_URI_PERMISSION,
            )
        } catch (_: Exception) {
            state.value = state.value.copy(status = "Android did not keep folder access. Choose it again and allow access.")
            return
        }
        val prefs = getApplication<Application>().getSharedPreferences("xortify", 0)
        prefs.edit().putString("selected_tree", uri.toString()).apply()
        val root = runCatching { DocumentFile.fromTreeUri(getApplication(), uri) }.getOrNull()
        journal.writableDatabase
        state.value = state.value.copy(
            treeUri = uri,
            folderLabel = root?.name ?: "Selected local folder",
            moves = emptyList(), fileCount = 0, duplicates = emptyList(), emptyFolders = emptyList(), largeFiles = emptyList(),
            status = "Folder ready. Press Scan folder to preview suggestions.", error = null,
        )
        refreshActivity()
    }

    fun setPage(page: AppPage) {
        state.value = state.value.copy(page = page)
        if (page == AppPage.Activity) refreshActivity()
    }

    fun toggle(id: String) {
        state.value = state.value.copy(moves = state.value.moves.map { if (it.id == id) it.copy(selected = !it.selected) else it })
    }

    fun selectAll(checked: Boolean) {
        state.value = state.value.copy(moves = state.value.moves.map { if (it.moved) it else it.copy(selected = checked) })
    }

    fun scan() {
        val tree = state.value.treeUri ?: run {
            state.value = state.value.copy(status = "Choose a folder first.")
            return
        }
        state.value = state.value.copy(busy = true, error = null, status = "Scanning selected folder…")
        viewModelScope.launch {
            try {
                val report = withContext(Dispatchers.IO) { organizer.scan(tree, ::setStatus) }
                state.value = state.value.withReport(report).copy(
                    busy = false,
                    status = "${report.fileCount} files scanned · ${report.moves.size} suggestions · preview only, nothing moved${if (report.errors > 0) " · ${report.errors} unreadable items skipped" else ""}${report.notes.firstOrNull()?.let { " · $it" } ?: ""}",
                    modelInstalled = isModelInstalled(getApplication<Application>().filesDir),
                )
            } catch (error: Exception) {
                state.value = state.value.copy(busy = false, error = error.message ?: "Scan failed.", status = "Scan could not finish.")
            }
        }
    }

    fun installModel() {
        if (state.value.busy) return
        state.value = state.value.copy(busy = true, error = null, status = "Downloading the 4.9 MiB image model…")
        viewModelScope.launch {
            try {
                withContext(Dispatchers.IO) {
                    installLocalModel(getApplication<Application>().filesDir) { done ->
                        setStatus("Downloading local image AI · ${formatBytes(done)} of 4.9 MiB")
                    }
                }
                state.value = state.value.copy(busy = false, modelInstalled = true, status = "Image AI installed. Photo analysis now runs on this phone.")
            } catch (error: Exception) {
                state.value = state.value.copy(busy = false, modelInstalled = false, error = error.message ?: "Model download failed.", status = "Image AI could not be installed.")
            }
        }
    }

    fun moveSelected() {
        val tree = state.value.treeUri ?: return
        val selected = state.value.moves.filter { it.selected && !it.moved }
        if (selected.isEmpty() || state.value.busy) return
        state.value = state.value.copy(busy = true, error = null, status = "Checking files before moving…")
        viewModelScope.launch {
            try {
                val result = withContext(Dispatchers.IO) { organizer.moveSelected(selected, tree, ::setStatus) }
                val report = if (result.movedIds.isNotEmpty()) withContext(Dispatchers.IO) { organizer.scan(tree, ::setStatus) } else null
                val summary = buildString {
                    append("Moved ${result.movedIds.size} items")
                    if (result.errors.isNotEmpty()) append(" · ${result.errors.size} skipped; review details")
                    append(" · Undo is available in Activity")
                }
                state.value = if (report != null) state.value.withReport(report).copy(busy = false, status = summary)
                else state.value.copy(busy = false, status = summary)
                if (result.errors.isNotEmpty()) state.value = state.value.copy(error = result.errors.take(4).joinToString("\n"))
            } catch (error: Exception) {
                state.value = state.value.copy(busy = false, error = error.message ?: "Move could not finish.", status = "Nothing else was moved.")
            }
            refreshActivity()
        }
    }

    fun undo() {
        val tree = state.value.treeUri
        if (tree == null || state.value.busy) return
        state.value = state.value.copy(busy = true, error = null, status = "Checking the latest move…")
        viewModelScope.launch {
            try {
                val (count, error) = withContext(Dispatchers.IO) { organizer.undoLatest(tree, ::setStatus) }
                val report = if (count > 0) withContext(Dispatchers.IO) { organizer.scan(tree, ::setStatus) } else null
                state.value = if (report != null) state.value.withReport(report).copy(busy = false, status = "Restored $count items to their original folders.")
                else state.value.copy(busy = false, status = error ?: "There are no completed moves to undo.")
                if (error != null) state.value = state.value.copy(error = error)
            } catch (error: Exception) {
                state.value = state.value.copy(busy = false, error = error.message ?: "Undo could not finish.", status = "Undo stopped safely.")
            }
            refreshActivity()
        }
    }

    private fun refreshActivity() {
        val lines = runCatching { journal.activityLines(state.value.treeUri) }.getOrDefault(emptyList())
        state.value = state.value.copy(activity = lines)
    }

    private fun setStatus(message: String) {
        mainHandler.post { if (state.value.busy) state.value = state.value.copy(status = message) }
    }

    private fun XortifyState.withReport(report: ScanReport): XortifyState = copy(
        moves = report.moves,
        fileCount = report.fileCount,
        emptyFolders = report.emptyFolders,
        largeFiles = report.largeFiles,
        duplicates = report.duplicates,
        activity = runCatching { journal.activityLines(state.value.treeUri) }.getOrDefault(emptyList()),
    )

    companion object {
        private fun initialState(application: Application): XortifyState {
            val tree = application.getSharedPreferences("xortify", 0).getString("selected_tree", null)?.let(Uri::parse)
                ?.takeIf { it.authority == "com.android.externalstorage.documents" }
            val label = tree?.let { uri -> runCatching { DocumentFile.fromTreeUri(application, uri)?.name }.getOrNull() }
                ?: "Choose a folder to explore"
            return XortifyState(
                treeUri = tree,
                folderLabel = label,
                modelInstalled = isModelInstalled(application.filesDir),
            )
        }
    }
}
