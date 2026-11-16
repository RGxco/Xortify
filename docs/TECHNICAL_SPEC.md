# Xortify technical specification — v0.1

## 1. Product scope

Xortify is a local-first Windows desktop organizer built with Python and PySide6. It scans a selected directory, explains proposed placements, groups familiar photo subjects with an optional local model, identifies common project folders as complete units, and moves only items the user approves.

The scan and plan are read-only. The review screen is the decision point: every proposed move has a selection switch and an editable destination. Applying a plan writes a SQLite journal first and supports undo.

### In scope

- Recursive scan of one selected directory without following symlinks or reparse points.
- File classification into Images, Videos, Documents, Audio, Archives, Code, Installers, and Other.
- Local file metadata, SHA-256 exact duplicate groups, empty directories, large files, and unreadable paths.
- Optional CPU image analysis using a downloaded quantized ONNX model.
- Name/folder cue placement suggestions and learning from completed approved destinations.
- Common project/repository detection. A recognized project folder is represented by one folder move, and its children are excluded from the per-file move plan.
- Collision-safe reversible file and folder moves with journal recovery.
- Review, selection, destination editing, findings, history, and undo in a Frutiger Aero PySide6 UI.
- All scan data and file analysis remain on the user's PC. The only network operation is an explicit download of the model weights.

### Not implemented in v0.1

- Video frame or scene analysis.
- OCR, document text extraction, document understanding, face recognition, or semantic search.
- User-prompted open-vocabulary image understanding or personal identity recognition.
- Automatic delete, duplicate cleanup, archive extraction, file watching, or cloud sync.

## 2. User flow and safety boundary

1. The user selects a directory and starts a background scan.
2. The scanner records metadata, classification, hashes, cleanup findings, and common project roots.
3. If the model is installed, a worker analyzes eligible loose images locally.
4. The planner creates category/topic file moves and one folder-level move per recognized project. The selected scan root itself is never proposed for movement.
5. The user reviews the plan, switches off anything unwanted, and can edit destinations inside the selected root.
6. On confirmation, Xortify rechecks each file hash or project tree fingerprint, journals the intent, chooses a collision-free destination, then moves and records the result.
7. Undo walks journal entries in reverse and restores each moved item. An occupied original path receives a numbered alternative.

No files move during steps 1–5. Findings never trigger deletion.

## 3. Architecture

~~~text
src/xortify/
  __main__.py       application entry point
  main_window.py    PySide6 review, findings, progress, history, undo
  workers.py        scan, action, and model-download QThreads
  models.py         FileRecord, ScanResult, PlanItem, operation results
  classifier.py     signatures, extensions, and MIME heuristics
  intelligence.py   local name/folder cues and approved-placement learner
  vision.py         verified model download, CPU ONNX inference, topic mapping
  bundles.py        project marker detection and tree fingerprinting
  scanner.py        read-only walk, metadata, SHA-256, findings
  planner.py        image topics, category destinations, project-unit moves
  database.py       SQLite snapshots, operation journal, schema migration
  operations.py     validation, collision-safe moves, undo/rollback
  assets/
    imagenet_labels.txt
~~~

Scanning, planning, bundles, and model inference are independent of Qt. PySide6 runs slow work in QThreads. SQLite calls use short-lived connections so a background worker does not share a connection with the UI thread.

## 4. Scanning and deterministic classification

The scanner walks the selected root recursively, skips symlinked/reparse entries, reads up to 8 KiB for file signatures, reads local metadata, and hashes each readable file in 1 MiB chunks. Equal SHA-256 values form exact duplicate groups.

Signatures take precedence over extensions where recognizable. Package-like documents such as DOCX, XLSX, and PPTX are not treated as generic ZIP archives. Extensions are the fallback for file types without distinctive signatures; Python's local MIME database is the final hint.

The scanner also records empty directories, files at least 500 MiB, and unreadable items. It does not inspect archive contents and does not treat file classification as a safety verdict.

## 5. Optional photo grouping

### Model and runtime

The optional image model is MediaPipe EfficientNet-Lite0 INT8/UINT8 ONNX from KETI Software Platform Team. The model file is 5,148,096 bytes (about 4.91 MiB), accepts a 224×224 RGB uint8 image, and predicts one of 1,000 ImageNet classes.

When requested, Xortify downloads the photo-grouping model over HTTPS, checks its size and SHA-256 digest, and installs it in:

~~~text
%LOCALAPPDATA%\Xortify\models
~~~

After installation, no internet connection is needed for inference. ONNX Runtime uses CPUExecutionProvider with one inference thread. Pillow applies EXIF orientation, converts to RGB, and center-crops/resizes. NumPy prepares one image at a time, keeping peak memory modest. The optional Python dependencies are installed with the vision extra: NumPy, onnxruntime, and Pillow.

Selected photo files, names, hashes, predictions, and scan results are never sent to the model host. Only the model artifact is downloaded. The model is not loaded during app startup unless a scan finds it installed and eligible images are present.

### Placement mapping

Xortify skips image inference inside recognized project folders. For other images, it uses the top model class when the output confidence reaches 0.10. Suitable class IDs map to broad folders such as Cats, Dogs, Birds, Animals, Food, Vehicles, Nature, and Sports. Images with a mapped topic from different source folders converge into one reviewed collection folder, with numbered filenames on collisions. A label with no supported broad mapping or a low score leaves the regular name/folder suggestion in place.

The classifier chooses from a fixed list of 1,000 labels, so results are broad suggestions and can be wrong. It does not support custom categories or process video and document contents.

### Commercial-release gate

The converted model card lists Apache 2.0 for the model artifact. ImageNet's separate access terms state non-commercial research and educational restrictions. Model-file licensing and training-data terms are distinct. Before a paid release, obtain a commercial rights review and clearance for this checkpoint or replace it with a model and training data whose commercial terms are confirmed. The active review is recorded in THIRD_PARTY_NOTICES.md.

## 6. Project-folder integrity

The scanner recognizes common project markers, including pyproject.toml, package.json, Cargo.toml, go.mod, Maven/Gradle files, Composer, CMake/Meson, Python setup files, Visual Studio project/solution files, Xcode project bundles, Unreal project files, and a .git directory. A generic requirements.txt alone is intentionally not enough.

Nested markers under an already-recognized project are covered by the outer root. If the selected scan root is itself a project, its files are all protected from per-file planning and the root is not moved.

Each nested project becomes one folder PlanItem targeting Code/Projects/<project name>. Files within it are not separately proposed, regardless of extension. Its journal entry records item_type=folder, aggregate size, and a tree fingerprint built from sorted relative paths and the SHA-256 of each scanned file. Before moving, Xortify re-hashes the current tree and rejects it if contents or file paths changed after the scan.

The move renames the complete directory as one item, preserving its internal structure and empty directories. Undo moves the complete directory back. An occupied destination is given a numbered name. Folder detection is marker-based, so unusual projects without a supported marker can still need user review.

## 7. Placement planner

The planner combines:

- deterministic category destination rules;
- curated filename and folder-name cues, such as invoice → Receipts and screenshot → Screenshots;
- up to 500 locally stored approved placement examples;
- the optional image model's mapped photo topic; and
- indivisible folder moves for recognized code projects.

Low-signal files keep the simpler category suggestion. Vision-tagged images flatten under a common topic directory so visually similar photos from different source folders can be gathered together. Other files preserve their relative path under the category/topic destination.

Every destination remains editable inside the selected root. The app prevents moving a project into itself. A user approval is required before the learner stores an adjusted placement.

## 8. Persistence and operation journal

The database is stored at %LOCALAPPDATA%\Xortify\xortify.sqlite3 on Windows, outside the selected directory.

| Table | Purpose |
| --- | --- |
| scans | Selected root, timestamps, and scan counts. |
| scan_files | Path, relative path, size, modified time, category, MIME hint, and SHA-256. |
| empty_directories | Empty paths reported by a scan. |
| operations | Root, timestamps, operation state, and errors. |
| operation_items | Source/destination, relative path, size, checksum/fingerprint, category, item type, status, error, and undo path. |
| placement_examples | Up to 500 local feature/topic examples from approved placements. |

Existing databases migrate the operation_items table by adding an item_type column with a default of file.

For each selected item, journal state progresses through pending → moving → moved or failed. The moving intent is committed before filesystem mutation. At startup, in-flight operations are reconciled from source/destination presence. Undo progresses through undoing → undone or undo_failed and processes confirmed moves in reverse order.

The journal supports normal undo and process-interruption recovery. It is not a backup or a filesystem/database-wide atomic transaction.

## 9. Filesystem rules

- Scanning opens content only for reading and writes no markers into the selected folder.
- Symlink and reparse entries are not traversed.
- Source and destination paths must remain under the selected root.
- File content hashes or project tree fingerprints are checked again before a move.
- Existing destination names are not intentionally replaced; a numbered alternative is chosen.
- Project folders are renamed whole. No project child is moved separately.
- The journal is written before each move; undo restores to an unoccupied numbered path when necessary.
- Nothing is automatically deleted. Findings are informational.

## 10. UI and dependency setup

The main window has a Frutiger Aero visual style and includes:

- folder selection, scan progress, scan metrics, and optional model download/status;
- review plan with per-item switches, editable paths, confidence/cue details, project-folder rows, Move confirmation, and Undo;
- Findings for duplicates, large files, empty folders, and unreadable paths; and
- recent activity.

The privacy badge explains that photos stay on the PC and the separate model download is optional. Once installed, photo grouping works offline.

Python 3.10+, PySide6 6.8+, and setuptools are required for the desktop. Install the UI and optional photo-grouping dependencies with:

~~~powershell
python -m pip install -e ".[dev,vision]"
python -m xortify
python -m pytest
~~~

The automated suite uses temporary directories and SQLite databases. It covers classifier hints, read-only scanning, SHA-256 duplicates, project-folder plans and undo, collision handling, changed-source rejection, placement learning, UI selection/editing, image topic mapping, and offline model inference when the optional model is installed.

## 11. Next local-analysis extensions

Later releases can add opt-in document text/OCR, video key-frame sampling, embeddings, or user-defined visual categories. Each adapter should have a separate permission, bounded CPU/memory use, explicit model identity, source/data license notes, and tests proving it remains local. A feature should not be advertised until it is implemented and verified.
