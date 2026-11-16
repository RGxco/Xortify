package com.xortify.app

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.activity.viewModels
import androidx.compose.runtime.getValue

class MainActivity : ComponentActivity() {
    private val viewModel: XortifyViewModel by viewModels()

    private val chooseFolder = registerForActivityResult(ActivityResultContracts.OpenDocumentTree()) { uri ->
        uri?.let(viewModel::selectTree)
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            val state by viewModel.state
            XortifyTheme {
                XortifyScreen(
                    state = state,
                    onBrowse = { chooseFolder.launch(null) },
                    onScan = viewModel::scan,
                    onInstallAi = viewModel::installModel,
                    onPage = viewModel::setPage,
                    onToggle = viewModel::toggle,
                    onSelectAll = viewModel::selectAll,
                    onMove = viewModel::moveSelected,
                    onUndo = viewModel::undo,
                    onDismissError = { viewModel.state.value = viewModel.state.value.copy(error = null) },
                )
            }
        }
    }
}
