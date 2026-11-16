package com.xortify.app

import android.content.Context
import android.net.Uri
import android.os.Build
import android.provider.DocumentsContract
import androidx.documentfile.provider.DocumentFile
import java.io.InputStream
import java.security.MessageDigest
import java.util.Locale
import java.util.UUID

private data class FileFound(
    val uri: Uri,
    val parent: Uri,
    val name: String,
    val path: String,
    val size: Long,
    val category: String,
    val hash: String,
    val project: ProjectFound?,
    var guess: VisualGuess? = null,
)

private data class ProjectFound(val uri: Uri, val parent: Uri, val name: String, val path: String)

class SafOrganizer(private val context: Context, private val journal: MoveJournal) {
    private val resolver = context.contentResolver

    fun scan(treeUri: Uri, onProgress: (String) -> Unit): ScanReport {
        require(treeUri.authority == "com.android.externalstorage.documents") {
            "Choose a folder in phone storage or an SD card so Xortify can keep everything local."
        }
        val root = DocumentFile.fromTreeUri(context, treeUri) ?: error("Android could not open this folder. Choose it again.")
        if (!root.isDirectory) error("Choose a folder rather than a single file.")
        val files = mutableListOf<FileFound>()
        val projects = linkedMapOf<String, ProjectFound>()
        val emptyFolders = mutableListOf<String>()
        val largeFiles = mutableListOf<Pair<String, Long>>()
        var errors = 0
        val rootChildren = safeChildren(root)
        val rootProject = isProjectMarker(
            rootChildren.filter { it.isFile }.mapNotNull { it.name }.toSet(),
            rootChildren.filter { it.isDirectory }.mapNotNull { it.name }.toSet(),
        )
        val rootProjectInfo = if (rootProject) ProjectFound(root.uri, root.uri, root.name ?: "Selected project", "") else null

        fun walk(folder: DocumentFile, relative: String, activeProject: ProjectFound?, protectRoot: Boolean) {
            val children = safeChildren(folder)
            if (children.isEmpty() && relative.isNotEmpty()) emptyFolders += relative
            if (activeProject == null && !protectRoot && isProjectMarker(
                    children.filter { it.isFile }.mapNotNull { it.name }.toSet(),
                    children.filter { it.isDirectory }.mapNotNull { it.name }.toSet(),
                )) {
                val project = ProjectFound(folder.uri, folder.parentFile?.uri ?: root.uri, folder.name ?: "Project", relative)
                projects[project.uri.toString()] = project
                children.forEach { child ->
                    val childName = child.name ?: return@forEach
                    val childPath = "$relative/$childName"
                    if (child.isDirectory) walk(child, childPath, project, false)
                    else if (child.isFile) addFile(child, folder, childPath, project)?.let(files::add) ?: run { errors++ }
                }
                return
            }
            for (child in children) {
                val name = child.name ?: continue
                val path = if (relative.isEmpty()) name else "$relative/$name"
                if (child.isDirectory) walk(child, path, activeProject, false)
                else if (child.isFile) {
                    val found = addFile(child, folder, path, activeProject)
                    if (found == null) errors++ else {
                        files += found
                        if (found.size >= 500L * 1024 * 1024) largeFiles += path to found.size
                        if (files.size % 20 == 0) onProgress("Checking ${files.size} files…")
                    }
                }
            }
        }

        rootChildren.forEach { child ->
            val name = child.name ?: return@forEach
            if (child.isDirectory) walk(child, name, rootProjectInfo, false)
            else if (child.isFile) {
                val found = addFile(child, root, name, rootProjectInfo)
                if (found == null) errors++ else {
                    files += found
                    if (found.size >= 500L * 1024 * 1024) largeFiles += name to found.size
                    if (files.size % 20 == 0) onProgress("Checking ${files.size} files…")
                }
            }
        }

        val vision = if (isModelInstalled(context.filesDir)) try {
            LocalVision(context.filesDir, resolver, context.assets, context.cacheDir)
        } catch (_: Exception) { null } else null
        if (vision != null) {
            files.filter { it.category == "Images" && it.project == null }.forEachIndexed { index, file ->
                try { file.guess = vision.predict(file.uri) } catch (_: Exception) { }
                if ((index + 1) % 10 == 0) onProgress("Local photo scan ${index + 1}…")
            }
            vision.close()
        }

        val projectHashes = projects.values.mapNotNull { project ->
            val entries = files.filter { it.project?.uri == project.uri }
            if (entries.isEmpty()) null else project.uri.toString() to fingerprint(entries.map { (it.path.removePrefix(project.path).trimStart('/') to it.hash) })
        }.toMap()
        val moves = mutableListOf<PlannedMove>()
        for (project in projects.values) {
            if (project.path.equals("Projects/${project.name}", ignoreCase = true)) continue
            val hash = projectHashes[project.uri.toString()] ?: continue
            if (hash.isBlank()) continue
            moves += PlannedMove(
                id = project.uri.toString(), uri = project.uri, parentUri = project.parent, name = project.name,
                relativePath = project.path.ifBlank { project.name }, category = "Projects",
                destination = "Projects/${project.name}", size = files.filter { it.project?.uri == project.uri }.sumOf { it.size },
                sha256 = hash, isDirectory = true, detail = "Complete project folder stays together",
            )
        }
        for (file in files) {
            if (file.project != null) continue
            val topic = file.guess?.takeIf { it.confidence >= 0.10f }?.topic
            val destination = if (topic != null && file.category == "Images") "Images/$topic/${file.name}" else "${file.category}/${file.name}"
            val guessLabel = file.guess?.let { "${it.label} · local AI" }.orEmpty()
            if (file.path.equals(destination, ignoreCase = true)) continue
            moves += PlannedMove(
                id = file.uri.toString(), uri = file.uri, parentUri = file.parent, name = file.name,
                relativePath = file.path, category = file.category, destination = destination, size = file.size,
                sha256 = file.hash, visualLabel = file.guess?.label,
                detail = if (guessLabel.isNotEmpty()) guessLabel else "Category only",
            )
        }
        val duplicates = files.filter { it.hash.isNotBlank() }.groupBy { it.hash }.values
            .filter { it.size > 1 }
            .map { group -> DuplicateGroup(group.first().hash, group.map { it.path }, group.first().size) }
        onProgress("Scan complete: ${files.size} files checked.")
        return ScanReport(
            moves = moves.sortedBy { it.relativePath.lowercase(Locale.ROOT) },
            fileCount = files.size,
            emptyFolders = emptyFolders.sorted(),
            largeFiles = largeFiles.sortedByDescending { it.second },
            duplicates = duplicates.sortedByDescending { it.locations.size },
            errors = errors,
            notes = if (rootProject) listOf("The selected folder looks like a code project. Xortify kept its files together.") else emptyList(),
        )
    }

    private fun addFile(document: DocumentFile, parent: DocumentFile, path: String, project: ProjectFound?): FileFound? = try {
        val size = document.length().coerceAtLeast(0)
        val header = resolver.openInputStream(document.uri)?.use { input ->
            val buffer = ByteArray(8192)
            val count = input.read(buffer)
            if (count <= 0) ByteArray(0) else buffer.copyOf(count)
        } ?: ByteArray(0)
        val category = classify(document.name ?: path.substringAfterLast('/'), header, document.type)
        val hash = hashUri(document.uri)
        FileFound(document.uri, parent.uri, document.name ?: path.substringAfterLast('/'), path, size, category, hash, project)
    } catch (_: Exception) { null }

    private fun safeChildren(folder: DocumentFile): List<DocumentFile> = try {
        folder.listFiles().sortedBy { it.name?.lowercase(Locale.ROOT) ?: "" }
    } catch (_: Exception) { emptyList() }

    private fun hashUri(uri: Uri): String {
        val digest = MessageDigest.getInstance("SHA-256")
        resolver.openInputStream(uri)?.use { stream -> stream.updateDigest(digest) } ?: error("Cannot read selected file")
        return digest.digest().joinToString("") { "%02x".format(it) }
    }

    private fun InputStream.updateDigest(digest: MessageDigest) {
        val chunk = ByteArray(256 * 1024)
        while (true) {
            val count = read(chunk)
            if (count < 0) break
            digest.update(chunk, 0, count)
        }
    }

    private fun fingerprint(entries: List<Pair<String, String>>): String {
        val digest = MessageDigest.getInstance("SHA-256")
        entries.sortedBy { it.first.lowercase(Locale.ROOT) }.forEach { (path, hash) ->
            digest.update("F\u0000".toByteArray())
            digest.update(path.toByteArray(Charsets.UTF_8))
            digest.update(0.toByte())
            digest.update(hash.toByteArray(Charsets.US_ASCII))
            digest.update(0.toByte())
        }
        return digest.digest().joinToString("") { "%02x".format(it) }
    }

    fun moveSelected(items: List<PlannedMove>, treeUri: Uri, onProgress: (String) -> Unit): MoveBatchResult {
        val root = DocumentFile.fromTreeUri(context, treeUri) ?: error("The selected folder is no longer available.")
        val groupId = UUID.randomUUID().toString()
        var movedCount = 0
        val messages = mutableListOf<String>()
        val movedIds = mutableSetOf<String>()
        for ((index, item) in items.withIndex()) {
            onProgress("Moving ${index + 1} of ${items.size}…")
            var journalId: Long? = null
            var journaledAsMoved = false
            try {
                if (item.isDirectory) {
                    val source = documentForUri(root, treeUri, item.uri) ?: error("Project folder is unavailable")
                    val currentHash = hashTree(source)
                    require(currentHash == item.sha256) { "Project changed after scanning; skipped ${item.name}." }
                } else {
                    require(hashUri(item.uri) == item.sha256) { "File changed after scanning; skipped ${item.name}." }
                }
                val destinationParts = item.destination.split('/').dropLast(1).filter(String::isNotBlank)
                val destinationParent = ensureDirectories(root, destinationParts)
                val wantedName = item.destination.substringAfterLast('/')
                val targetName = uniqueName(destinationParent, wantedName)
                journalId = journal.prepare(groupId, treeUri, item, targetName)
                journal.setDestination(journalId, destinationParent.uri)
                val movedUri = moveDocument(item, destinationParent, targetName)
                journal.complete(journalId, movedUri)
                journaledAsMoved = true
                val afterHash = if (item.isDirectory) hashTree(documentForUri(root, treeUri, movedUri) ?: error("Moved project cannot be checked")) else hashUri(movedUri)
                require(afterHash == item.sha256) { "Moved item did not match its scan hash: ${item.name}." }
                movedCount++
                movedIds += item.id
            } catch (error: Exception) {
                if (!journaledAsMoved) journalId?.let { journal.fail(it, error.message ?: "Move failed") }
                messages += error.message ?: "Could not move ${item.name}."
            }
        }
        return MoveBatchResult(movedIds, messages)
    }

    private fun moveDocument(item: PlannedMove, destinationParent: DocumentFile, targetName: String): Uri {
        val direct = if (Build.VERSION.SDK_INT >= 24) try {
            DocumentsContract.moveDocument(resolver, item.uri, item.parentUri, destinationParent.uri)
        } catch (_: Exception) { null } else null
        if (direct != null) {
            if (targetName == item.name) return direct
            return try { DocumentsContract.renameDocument(resolver, direct, targetName) ?: direct }
            catch (_: Exception) { direct }
        }
        if (item.isDirectory) error("Android could not safely move this project folder. The original project was left in place.")

        val created = destinationParent.createFile(mimeFor(targetName), targetName)
            ?: error("Android could not create a destination for ${item.name}.")
        var verifiedCopy = false
        try {
            resolver.openInputStream(item.uri)?.use { input ->
                resolver.openOutputStream(created.uri, "w")?.use { output -> input.copyTo(output, 256 * 1024) }
                    ?: error("Android could not write ${item.name}.")
            } ?: error("Android could not read ${item.name}.")
            require(hashUri(created.uri) == item.sha256) { "The copied file failed its SHA-256 check." }
            verifiedCopy = true
            val source = DocumentFile.fromSingleUri(context, item.uri) ?: error("The original file is unavailable.")
            if (!source.delete()) error("The new copy passed its SHA-256 check, but Android could not remove the original. Both copies were kept.")
            return created.uri
        } catch (error: Exception) {
            if (!verifiedCopy) created.delete()
            throw error
        }
    }

    fun undoLatest(treeUri: Uri, onProgress: (String) -> Unit): Pair<Int, String?> {
        val rows = journal.latestGroup(treeUri)
        if (rows.isEmpty()) return 0 to "There are no completed moves to undo."
        val root = DocumentFile.fromTreeUri(context, treeUri) ?: return 0 to "The selected folder is no longer available."
        var undone = 0
        var firstError: String? = null
        rows.forEachIndexed { index, row ->
            onProgress("Undoing ${index + 1} of ${rows.size}…")
            journal.setState(row.id, "undoing")
            try {
                val sourceUri = row.destination ?: error("The journal entry has no destination.")
                val source = documentForUri(root, treeUri, sourceUri) ?: error("The moved item is no longer available.")
                val originalParent = documentForUri(root, treeUri, row.sourceParent)
                    ?: error("The original folder is no longer available.")
                val restoreName = uniqueName(originalParent, row.originalName)
                val currentHash = if (row.isDirectory) hashTree(source) else hashUri(sourceUri)
                require(currentHash == row.sha256) { "${row.targetName} changed after it was moved; kept it in place." }
                val moved = if (Build.VERSION.SDK_INT >= 24) try {
                    DocumentsContract.moveDocument(resolver, sourceUri, row.destinationParent, originalParent.uri)
                } catch (_: Exception) { null } else null
                val restoredUri = if (moved != null) {
                    if (restoreName == row.targetName) moved else DocumentsContract.renameDocument(resolver, moved, restoreName)
                        ?: error("Could not restore the original name; the item remains in its current location.")
                } else if (!row.isDirectory) {
                    val destination = originalParent.createFile(mimeFor(restoreName), restoreName)
                        ?: error("Could not restore ${row.originalName}.")
                    try {
                        resolver.openInputStream(sourceUri)?.use { input ->
                            resolver.openOutputStream(destination.uri, "w")?.use { output -> input.copyTo(output, 256 * 1024) }
                                ?: error("Could not write the restored file.")
                        } ?: error("Could not read the moved file.")
                        require(hashUri(destination.uri) == row.sha256) { "The restored copy did not pass its hash check." }
                        require(source.delete()) { "The original copy remains at the destination; no copy was discarded." }
                        destination.uri
                    } catch (error: Exception) { destination.delete(); throw error }
                } else error("Android could not safely move the project back. It remains in its current location.")
                val verified = if (row.isDirectory) hashTree(documentForUri(root, treeUri, restoredUri) ?: error("Restored project is unavailable")) else hashUri(restoredUri)
                require(verified == row.sha256) { "The restored item failed its SHA-256 check." }
                journal.setState(row.id, "undone")
                undone++
            } catch (error: Exception) {
                journal.setState(row.id, "done", error.message)
                if (firstError == null) firstError = error.message ?: "Undo could not complete."
            }
        }
        return undone to firstError
    }

    private fun hashTree(folder: DocumentFile): String {
        val entries = mutableListOf<Pair<String, String>>()
        fun walk(dir: DocumentFile, prefix: String) {
            dir.listFiles().sortedBy { it.name?.lowercase(Locale.ROOT) ?: "" }.forEach { child ->
                val name = child.name ?: ""
                val path = if (prefix.isEmpty()) name else "$prefix/$name"
                if (child.isDirectory) walk(child, path)
                else if (child.isFile) entries += path to hashUri(child.uri)
            }
        }
        walk(folder, "")
        return fingerprint(entries)
    }

    private fun documentForUri(root: DocumentFile, treeUri: Uri, wanted: Uri): DocumentFile? {
        val rootId = try { DocumentsContract.getTreeDocumentId(treeUri) } catch (_: Exception) { return null }
        val wantedId = try { DocumentsContract.getDocumentId(wanted) } catch (_: Exception) { return null }
        if (wantedId == rootId) return root
        val prefix = "$rootId/"
        if (!wantedId.startsWith(prefix)) return null
        val segments = wantedId.removePrefix(prefix).split('/').filter(String::isNotEmpty)
        var current = root
        for (segment in segments) {
            current = current.listFiles().firstOrNull { it.name == segment } ?: return null
        }
        return current
    }

    private fun ensureDirectories(root: DocumentFile, path: List<String>): DocumentFile {
        var current = root
        for (part in path) {
            val existing = current.listFiles().firstOrNull { it.isDirectory && it.name.equals(part, ignoreCase = true) }
            current = existing ?: current.createDirectory(part) ?: error("Could not create the $part folder inside your selection.")
        }
        return current
    }

    private fun uniqueName(parent: DocumentFile, requested: String): String {
        val names = parent.listFiles().mapNotNull { it.name?.lowercase(Locale.ROOT) }.toHashSet()
        if (requested.lowercase(Locale.ROOT) !in names) return requested
        val dot = requested.lastIndexOf('.')
        val stem = if (dot > 0) requested.substring(0, dot) else requested
        val suffix = if (dot > 0) requested.substring(dot) else ""
        var number = 2
        while ("$stem ($number)$suffix".lowercase(Locale.ROOT) in names) number++
        return "$stem ($number)$suffix"
    }
}
