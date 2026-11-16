package com.xortify.app

import android.content.Context
import android.database.sqlite.SQLiteDatabase
import android.database.sqlite.SQLiteOpenHelper
import android.net.Uri

data class JournalMove(
    val id: Long,
    val groupId: String,
    val sourceParent: Uri,
    val destinationParent: Uri,
    val destination: Uri?,
    val originalName: String,
    val targetName: String,
    val sha256: String,
    val isDirectory: Boolean,
    val state: String,
)

class MoveJournal(context: Context) : SQLiteOpenHelper(context, "xortify-android.sqlite3", null, 1) {
    override fun onCreate(db: SQLiteDatabase) {
        db.execSQL("""
            CREATE TABLE move_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id TEXT NOT NULL,
                root_uri TEXT NOT NULL,
                source_parent TEXT NOT NULL,
                destination_parent TEXT NOT NULL,
                destination_uri TEXT,
                original_name TEXT NOT NULL,
                target_name TEXT NOT NULL,
                sha256 TEXT NOT NULL,
                is_directory INTEGER NOT NULL,
                state TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                error TEXT
            )
        """.trimIndent())
        db.execSQL("CREATE INDEX move_log_group_id ON move_log(group_id, id)")
    }

    override fun onUpgrade(db: SQLiteDatabase, oldVersion: Int, newVersion: Int) = Unit

    fun prepare(group: String, rootUri: Uri, item: PlannedMove, targetName: String): Long = writableDatabase.let { db ->
        val values = android.content.ContentValues().apply {
            put("group_id", group)
            put("root_uri", rootUri.toString())
            put("source_parent", item.parentUri.toString())
            put("destination_parent", "")
            put("original_name", item.name)
            put("target_name", targetName)
            put("sha256", item.sha256)
            put("is_directory", if (item.isDirectory) 1 else 0)
            put("state", "pending")
            put("created_at", System.currentTimeMillis())
        }
        db.insertOrThrow("move_log", null, values)
    }

    fun setDestination(id: Long, targetParent: Uri) {
        writableDatabase.execSQL("UPDATE move_log SET destination_parent=? WHERE id=?", arrayOf(targetParent.toString(), id))
    }

    fun complete(id: Long, destination: Uri) {
        writableDatabase.execSQL("UPDATE move_log SET destination_uri=?, state='done' WHERE id=?", arrayOf(destination.toString(), id))
    }

    fun fail(id: Long, message: String) {
        writableDatabase.execSQL("UPDATE move_log SET state='failed', error=? WHERE id=?", arrayOf(message.take(500), id))
    }

    fun latestGroup(rootUri: Uri): List<JournalMove> {
        val db = readableDatabase
        val group = db.rawQuery("SELECT group_id FROM move_log WHERE state='done' AND root_uri=? ORDER BY id DESC LIMIT 1", arrayOf(rootUri.toString())).use { cursor ->
            if (cursor.moveToFirst()) cursor.getString(0) else return emptyList()
        }
        return db.rawQuery("SELECT * FROM move_log WHERE group_id=? AND root_uri=? AND state='done' ORDER BY id DESC", arrayOf(group, rootUri.toString())).use { cursor ->
            buildList {
                while (cursor.moveToNext()) add(cursor.toMove())
            }
        }
    }

    fun setState(id: Long, state: String, message: String? = null) {
        writableDatabase.execSQL("UPDATE move_log SET state=?, error=? WHERE id=?", arrayOf(state, message, id))
    }

    fun activityLines(rootUri: Uri?): List<String> = if (rootUri == null) emptyList() else readableDatabase.rawQuery(
        "SELECT group_id, COUNT(*), MAX(created_at) FROM move_log WHERE state='done' AND root_uri=? GROUP BY group_id ORDER BY MAX(id) DESC LIMIT 8", arrayOf(rootUri.toString())
    ).use { cursor ->
        buildList {
            while (cursor.moveToNext()) {
                val count = cursor.getInt(1)
                val time = java.text.DateFormat.getDateTimeInstance(java.text.DateFormat.MEDIUM, java.text.DateFormat.SHORT)
                    .format(java.util.Date(cursor.getLong(2)))
                add("Moved $count ${if (count == 1) "item" else "items"} · $time")
            }
        }
    }

    private fun android.database.Cursor.toMove(): JournalMove = JournalMove(
        id = getLong(getColumnIndexOrThrow("id")),
        groupId = getString(getColumnIndexOrThrow("group_id")),
        sourceParent = Uri.parse(getString(getColumnIndexOrThrow("source_parent"))),
        destinationParent = Uri.parse(getString(getColumnIndexOrThrow("destination_parent"))),
        destination = getString(getColumnIndexOrThrow("destination_uri"))?.let(Uri::parse),
        originalName = getString(getColumnIndexOrThrow("original_name")),
        targetName = getString(getColumnIndexOrThrow("target_name")),
        sha256 = getString(getColumnIndexOrThrow("sha256")),
        isDirectory = getInt(getColumnIndexOrThrow("is_directory")) != 0,
        state = getString(getColumnIndexOrThrow("state")),
    )
}
