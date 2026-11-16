package com.xortify.app

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Checkbox
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Divider
import androidx.compose.material3.FilledTonalButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

private val Lagoon = Color(0xff087c9c)
private val DeepBlue = Color(0xff124f70)
private val BodyBlue = Color(0xff315f78)
private val Aqua = Color(0xff1ab5bd)
private val Leaf = Color(0xff138251)
private val Ice = Color(0xffe5f9fc)
private val Frost = Color(0xfff8fdff)

@Composable
fun XortifyTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = lightColorScheme(
            primary = Lagoon,
            onPrimary = Color.White,
            secondary = Aqua,
            onSecondary = Color.White,
            tertiary = Leaf,
            background = Ice,
            surface = Frost,
            onSurface = DeepBlue,
            onBackground = DeepBlue,
            outline = Color(0xff9bcfdd),
            surfaceVariant = Color(0xffe1f4f8),
            onSurfaceVariant = BodyBlue,
        ),
        content = content,
    )
}

@Composable
fun XortifyScreen(
    state: XortifyState,
    onBrowse: () -> Unit,
    onScan: () -> Unit,
    onInstallAi: () -> Unit,
    onPage: (AppPage) -> Unit,
    onToggle: (String) -> Unit,
    onSelectAll: (Boolean) -> Unit,
    onMove: () -> Unit,
    onUndo: () -> Unit,
    onDismissError: () -> Unit,
) {
    var confirmMove by remember { mutableStateOf(false) }
    BoxWithConstraints(Modifier.fillMaxSize()) {
        val wide = maxWidth >= 780.dp
        val pagePadding = if (wide) 28.dp else 16.dp
        Box(Modifier.fillMaxSize().background(
            Brush.verticalGradient(listOf(Color(0xff91daf2), Color(0xffd3f6fa), Color(0xffa3dfd4)))
        ))
        Scaffold(
            containerColor = Color.Transparent,
            bottomBar = {
                if (!wide) {
                    Column {
                        if (state.page == AppPage.Review && state.moves.isNotEmpty()) {
                            ActionStrip(state = state, onMove = { confirmMove = true }, onUndo = onUndo, compact = true)
                        }
                        NavigationBar(containerColor = Color(0xffe9fafd).copy(alpha = 0.96f), tonalElevation = 8.dp) {
                            AppPage.entries.forEach { page ->
                                NavigationBarItem(
                                    selected = state.page == page,
                                    onClick = { onPage(page) },
                                    icon = { Text(page.symbol, fontSize = 19.sp, fontWeight = FontWeight.Bold) },
                                    label = { Text(page.label, maxLines = 1, fontSize = 11.sp) },
                                )
                            }
                        }
                    }
                }
            },
        ) { insets ->
            Row(Modifier.fillMaxSize().padding(insets)) {
                if (wide) {
                    NavigationSidebar(state.page, onPage)
                }
                LazyColumn(
                    modifier = Modifier.weight(1f).fillMaxSize(),
                    contentPadding = PaddingValues(horizontal = pagePadding, vertical = 18.dp),
                    verticalArrangement = Arrangement.spacedBy(14.dp),
                ) {
                    item { BrandHeader(wide) }
                    item {
                        FolderCard(
                            state = state,
                            wide = wide,
                            onBrowse = onBrowse,
                            onScan = onScan,
                            onInstallAi = onInstallAi,
                        )
                    }
                    item { StatsCards(state = state, wide = wide) }
                    item { StatusCard(state) }
                    item {
                        PageHeading(state = state)
                    }
                    if (state.page == AppPage.Review) {
                        item {
                            ReviewToolbar(
                                count = state.moves.count { !it.moved },
                                selected = state.selectedCount,
                                busy = state.busy,
                                wide = wide,
                                onSelectAll = onSelectAll,
                                onMove = { confirmMove = true },
                            )
                        }
                        if (state.moves.isEmpty()) {
                            item { EmptyStateCard(state) }
                        } else {
                            items(state.moves, key = { it.id }) { move ->
                                MoveCard(move, wide = wide, onToggle = { onToggle(move.id) })
                            }
                        }
                    } else if (state.page == AppPage.Findings) {
                        item { FindingsContent(state) }
                    } else {
                        item { ActivityContent(state, onUndo) }
                    }
                }
            }
        }
        if (confirmMove) {
            AlertDialog(
                onDismissRequest = { confirmMove = false },
                title = { Text("Move selected items?") },
                text = { Text("Xortify will recheck each item, avoid name conflicts, and record the moves so you can undo them. Your original files are not changed during preview.") },
                confirmButton = {
                    Button(onClick = { confirmMove = false; onMove() }, enabled = state.selectedCount > 0 && !state.busy) { Text("Move ${state.selectedCount}") }
                },
                dismissButton = { TextButton(onClick = { confirmMove = false }) { Text("Keep reviewing") } },
                containerColor = Frost,
                shape = RoundedCornerShape(26.dp),
            )
        }
        state.error?.let { message ->
            AlertDialog(
                onDismissRequest = onDismissError,
                title = { Text("Xortify needs your attention") },
                text = { Text(message) },
                confirmButton = { TextButton(onClick = onDismissError) { Text("Got it") } },
                containerColor = Frost,
                shape = RoundedCornerShape(26.dp),
            )
        }
    }
}

@Composable
private fun NavigationSidebar(page: AppPage, onPage: (AppPage) -> Unit) {
    Surface(color = Color(0xffdff7fa).copy(alpha = 0.87f), shadowElevation = 8.dp) {
        Column(
            modifier = Modifier.width(100.dp).fillMaxSize().padding(vertical = 22.dp, horizontal = 9.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            AppPage.entries.forEach { item ->
                val selected = item == page
                Surface(
                    modifier = Modifier.clickable { onPage(item) },
                    shape = RoundedCornerShape(20.dp),
                    color = if (selected) Color.White else Color.Transparent,
                    border = if (selected) BorderStroke(1.dp, Color(0xff9ed7e3)) else null,
                ) {
                    Column(Modifier.width(78.dp).padding(vertical = 13.dp), horizontalAlignment = Alignment.CenterHorizontally) {
                        Text(item.symbol, color = Lagoon, fontSize = 21.sp, fontWeight = FontWeight.Bold)
                        Spacer(Modifier.height(5.dp))
                        Text(item.label.substringBefore(' '), color = DeepBlue, fontSize = 11.sp, fontWeight = FontWeight.SemiBold)
                    }
                }
            }
        }
    }
}

@Composable
private fun BrandHeader(wide: Boolean) {
    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.SpaceBetween, modifier = Modifier.fillMaxWidth()) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Box(
                Modifier.size(if (wide) 58.dp else 48.dp).shadow(7.dp, CircleShape)
                    .background(Brush.linearGradient(listOf(Color.White, Color(0xffa8ebed))), CircleShape),
                contentAlignment = Alignment.Center,
            ) {
                Text("X", color = Lagoon, fontSize = if (wide) 32.sp else 27.sp, fontWeight = FontWeight.Black)
            }
            Spacer(Modifier.width(13.dp))
            Column {
                Text("Xortify", color = DeepBlue, fontSize = if (wide) 32.sp else 28.sp, fontWeight = FontWeight.ExtraBold, letterSpacing = (-0.6).sp)
                Text("Fresh folders. Clear skies.", color = BodyBlue, fontSize = 13.sp)
            }
        }
        Surface(shape = CircleShape, color = Color(0xffd8f7d9), border = BorderStroke(1.dp, Color(0xff9bdaa8))) {
            Text("●  FILES STAY LOCAL", Modifier.padding(horizontal = 13.dp, vertical = 9.dp), color = Color(0xff23643a), fontSize = 10.sp, fontWeight = FontWeight.Bold)
        }
    }
}

@Composable
private fun FolderCard(state: XortifyState, wide: Boolean, onBrowse: () -> Unit, onScan: () -> Unit, onInstallAi: () -> Unit) {
    FrostCard {
        Column(verticalArrangement = Arrangement.spacedBy(11.dp)) {
            Text("Choose a folder to explore", color = DeepBlue, fontWeight = FontWeight.Bold, fontSize = 16.sp)
            if (wide) {
                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(9.dp)) {
                    FolderPath(state.folderLabel, Modifier.weight(1f))
                    OutlinedButton(onClick = onBrowse, enabled = !state.busy, shape = RoundedCornerShape(14.dp)) { Text("Browse…") }
                    Button(onClick = onScan, enabled = state.treeUri != null && !state.busy, shape = RoundedCornerShape(14.dp)) { Text("Scan folder") }
                }
            } else {
                FolderPath(state.folderLabel, Modifier.fillMaxWidth())
                Row(horizontalArrangement = Arrangement.spacedBy(9.dp), modifier = Modifier.fillMaxWidth()) {
                    OutlinedButton(onClick = onBrowse, enabled = !state.busy, modifier = Modifier.weight(1f), shape = RoundedCornerShape(14.dp)) { Text("Browse folder") }
                    Button(onClick = onScan, enabled = state.treeUri != null && !state.busy, modifier = Modifier.weight(1f), shape = RoundedCornerShape(14.dp)) { Text("Scan folder") }
                }
            }
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.SpaceBetween, modifier = Modifier.fillMaxWidth()) {
                Text("Selected folder only · no cloud connection", color = BodyBlue, fontSize = 12.sp)
                if (state.modelInstalled) {
                    Text("Image AI ready · on this phone", color = Leaf, fontSize = 11.sp, fontWeight = FontWeight.SemiBold)
                } else {
                    TextButton(onClick = onInstallAi, enabled = !state.busy) { Text("Install image AI · 4.9 MB", fontSize = 11.sp) }
                }
            }
        }
    }
}

@Composable
private fun FolderPath(value: String, modifier: Modifier) {
    Surface(modifier, shape = RoundedCornerShape(15.dp), color = Color.White.copy(alpha = 0.83f), border = BorderStroke(1.dp, Color(0xff9bd7e5))) {
        Text(value, Modifier.padding(horizontal = 14.dp, vertical = 12.dp), color = DeepBlue, maxLines = 1, overflow = TextOverflow.Ellipsis, fontSize = 14.sp)
    }
}

@Composable
private fun StatsCards(state: XortifyState, wide: Boolean) {
    val cards = listOf(
        "FILES SCANNED" to state.fileCount.toString(),
        "EXACT DUPLICATES" to state.duplicateCount.toString(),
        "LARGE FILES" to state.largeCount.toString(),
        "EMPTY FOLDERS" to state.emptyCount.toString(),
    )
    Column(verticalArrangement = Arrangement.spacedBy(9.dp)) {
        cards.chunked(if (wide) 4 else 2).forEach { row ->
            Row(horizontalArrangement = Arrangement.spacedBy(9.dp), modifier = Modifier.fillMaxWidth()) {
                row.forEach { (label, value) ->
                    FrostCard(Modifier.weight(1f)) {
                        Column {
                            Text(label, color = Lagoon, fontSize = 10.sp, letterSpacing = 0.7.sp, fontWeight = FontWeight.Bold)
                            Text(value, color = DeepBlue, fontSize = 28.sp, fontWeight = FontWeight.ExtraBold)
                            val foot = when (label) {
                                "EXACT DUPLICATES" -> "${state.duplicates.size} matching groups"
                                "LARGE FILES" -> "500 MiB or larger"
                                "EMPTY FOLDERS" -> "No automatic deletion"
                                else -> if (state.fileCount > 0) "Current scan" else "Ready to scan"
                            }
                            Text(foot, color = BodyBlue, fontSize = 11.sp)
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun StatusCard(state: XortifyState) {
    FrostCard {
        Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(9.dp)) {
                if (state.busy) CircularProgressIndicator(Modifier.size(17.dp), strokeWidth = 2.dp, color = Lagoon)
                else Text("●", color = Leaf, fontSize = 14.sp)
                Text(state.status, color = if (state.busy) Lagoon else Leaf, fontSize = 13.sp, fontWeight = FontWeight.SemiBold)
            }
            if (state.busy) LinearProgressIndicator(Modifier.fillMaxWidth(), color = Aqua, trackColor = Color(0xffd7f1f5))
        }
    }
}

@Composable
private fun PageHeading(state: XortifyState) {
    Column {
        Text(state.page.label, color = DeepBlue, fontSize = 20.sp, fontWeight = FontWeight.Bold)
        Text(
            when (state.page) {
                AppPage.Review -> "Review each suggestion before anything moves."
                AppPage.Findings -> "Useful cleanup clues. Xortify never deletes files or folders."
                AppPage.Activity -> "Your move journal stays on this device and supports undo."
            },
            color = BodyBlue,
            fontSize = 12.sp,
        )
    }
}

@Composable
private fun ReviewToolbar(
    count: Int,
    selected: Int,
    busy: Boolean,
    wide: Boolean,
    onSelectAll: (Boolean) -> Unit,
    onMove: () -> Unit,
) {
    FrostCard {
        if (wide) {
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.SpaceBetween, modifier = Modifier.fillMaxWidth()) {
                Column {
                    Text("Proposed organization", color = DeepBlue, fontWeight = FontWeight.Bold)
                    Text("$selected of $count proposed moves selected", color = BodyBlue, fontSize = 12.sp)
                }
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    OutlinedButton(onClick = { onSelectAll(true) }, enabled = count > 0 && !busy) { Text("Select all") }
                    OutlinedButton(onClick = { onSelectAll(false) }, enabled = count > 0 && !busy) { Text("Select none") }
                    Button(onClick = onMove, enabled = selected > 0 && !busy) { Text("Move selected") }
                }
            }
        } else {
            Column {
                Text("$selected of $count proposed moves selected", color = DeepBlue, fontWeight = FontWeight.SemiBold, fontSize = 13.sp)
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    OutlinedButton(onClick = { onSelectAll(true) }, enabled = count > 0 && !busy) { Text("Select all") }
                    OutlinedButton(onClick = { onSelectAll(false) }, enabled = count > 0 && !busy) { Text("Select none") }
                }
            }
        }
        if (count > 0) {
            Spacer(Modifier.height(9.dp))
            Text("The local photo model can group familiar subjects. Recognized code projects stay together as complete folders.", color = BodyBlue, fontSize = 11.sp)
        }
    }
}

@Composable
private fun MoveCard(move: PlannedMove, wide: Boolean, onToggle: () -> Unit) {
    FrostCard {
        Row(verticalAlignment = Alignment.Top, horizontalArrangement = Arrangement.spacedBy(10.dp)) {
            Switch(checked = move.selected && !move.moved, onCheckedChange = { onToggle() }, enabled = !move.moved)
            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(5.dp)) {
                Row(horizontalArrangement = Arrangement.SpaceBetween, modifier = Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                    Surface(shape = CircleShape, color = Color(0xffd7f2f5)) {
                        Text(move.category, Modifier.padding(horizontal = 10.dp, vertical = 5.dp), color = Lagoon, fontSize = 11.sp, fontWeight = FontWeight.Bold)
                    }
                    Text(formatBytes(move.size), color = BodyBlue, fontSize = 11.sp)
                }
                Text(move.name, color = DeepBlue, fontWeight = FontWeight.Bold, fontSize = 14.sp, maxLines = 1, overflow = TextOverflow.Ellipsis)
                if (wide) {
                    Row(horizontalArrangement = Arrangement.spacedBy(12.dp), modifier = Modifier.fillMaxWidth()) {
                        PathColumn("FROM", move.relativePath, Modifier.weight(1f))
                        PathColumn("PROPOSED LOCATION", move.destination, Modifier.weight(1f))
                    }
                } else {
                    PathColumn("CURRENT LOCATION", move.relativePath, Modifier.fillMaxWidth())
                    PathColumn("MOVE TO", move.destination, Modifier.fillMaxWidth())
                }
                Text(move.detail, color = BodyBlue, fontSize = 11.sp, maxLines = 1, overflow = TextOverflow.Ellipsis)
            }
        }
    }
}

@Composable
private fun PathColumn(label: String, value: String, modifier: Modifier) {
    Column(modifier) {
        Text(label, color = Lagoon, fontSize = 9.sp, letterSpacing = 0.6.sp, fontWeight = FontWeight.Bold)
        Text(value, color = BodyBlue, fontSize = 11.sp, maxLines = 1, overflow = TextOverflow.Ellipsis)
    }
}

@Composable
private fun EmptyStateCard(state: XortifyState) {
    FrostCard {
        Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Text(if (state.fileCount == 0) "Ready when you are" else "Everything is already organized", color = DeepBlue, fontWeight = FontWeight.Bold, fontSize = 17.sp)
            Text(
                if (state.fileCount == 0) "Choose a local folder, then scan to see a read-only preview." else "No loose files need moving in this folder. Check Findings for duplicates and empty folders.",
                color = BodyBlue,
                fontSize = 13.sp,
            )
        }
    }
}

@Composable
private fun FindingsContent(state: XortifyState) {
    Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
        if (state.duplicates.isEmpty() && state.largeFiles.isEmpty() && state.emptyFolders.isEmpty()) {
            EmptyStateCard(state)
        }
        state.duplicates.forEachIndexed { index, group ->
            FrostCard {
                Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                    Text("Exact match group ${index + 1} · ${group.locations.size} files", color = DeepBlue, fontWeight = FontWeight.Bold)
                    Text("${formatBytes(group.size)} each · SHA-256", color = BodyBlue, fontSize = 12.sp)
                    group.locations.forEach { Text("• $it", color = BodyBlue, fontSize = 11.sp, maxLines = 2, overflow = TextOverflow.Ellipsis) }
                }
            }
        }
        state.largeFiles.forEach { (path, size) ->
            FindingCard(title = "Large file · ${formatBytes(size)}", detail = path)
        }
        state.emptyFolders.forEach { path -> FindingCard(title = "Empty folder", detail = path) }
    }
}

@Composable
private fun ActivityContent(state: XortifyState, onUndo: () -> Unit) {
    Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
        FrostCard {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text("Move history", color = DeepBlue, fontWeight = FontWeight.Bold, fontSize = 16.sp)
                Text("Moves are recorded on this phone. Undo restores names and original folders when they are still available.", color = BodyBlue, fontSize = 12.sp)
                OutlinedButton(onClick = onUndo, enabled = state.activity.isNotEmpty() && !state.busy) { Text("Undo latest move") }
            }
        }
        if (state.activity.isEmpty()) FindingCard("No moves yet", "Approved moves will appear here.")
        state.activity.forEach { entry -> FindingCard("Completed move", entry) }
    }
}

@Composable
private fun FindingCard(title: String, detail: String) {
    FrostCard {
        Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Text(title, color = DeepBlue, fontWeight = FontWeight.Bold, fontSize = 13.sp)
            Text(detail, color = BodyBlue, fontSize = 12.sp, maxLines = 3, overflow = TextOverflow.Ellipsis)
        }
    }
}

@Composable
private fun ActionStrip(state: XortifyState, onMove: () -> Unit, onUndo: () -> Unit, compact: Boolean) {
    Surface(color = Color(0xfff4fdff).copy(alpha = 0.98f), shadowElevation = 10.dp) {
        Row(
            Modifier.fillMaxWidth().padding(horizontal = if (compact) 12.dp else 0.dp, vertical = 8.dp),
            horizontalArrangement = Arrangement.spacedBy(8.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text("${state.selectedCount} selected", Modifier.weight(1f), color = Leaf, fontSize = 12.sp, fontWeight = FontWeight.Bold, maxLines = 1)
            OutlinedButton(onClick = onUndo, enabled = state.activity.isNotEmpty() && !state.busy, contentPadding = PaddingValues(horizontal = 12.dp, vertical = 7.dp)) {
                Text("Undo", fontSize = 12.sp)
            }
            Button(
                onClick = onMove,
                enabled = state.selectedCount > 0 && !state.busy,
                shape = RoundedCornerShape(14.dp),
                contentPadding = PaddingValues(horizontal = 15.dp, vertical = 9.dp),
                colors = ButtonDefaults.buttonColors(containerColor = Lagoon),
            ) { Text(if (compact) "Move" else "Move selected items", fontWeight = FontWeight.Bold, fontSize = 12.sp) }
        }
    }
}

@Composable
private fun FrostCard(modifier: Modifier = Modifier, content: @Composable () -> Unit) {
    Card(
        modifier = modifier.fillMaxWidth().shadow(4.dp, RoundedCornerShape(20.dp)),
        shape = RoundedCornerShape(20.dp),
        colors = CardDefaults.cardColors(containerColor = Frost.copy(alpha = 0.94f)),
        border = BorderStroke(1.dp, Color.White.copy(alpha = 0.95f)),
        elevation = CardDefaults.cardElevation(defaultElevation = 1.dp),
    ) {
        Column(Modifier.padding(15.dp), content = { content() })
    }
}
