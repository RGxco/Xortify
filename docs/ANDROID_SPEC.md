# Xortify Android companion — v0.1

## Product scope

This is a native Android companion to the existing Windows desktop app. It is written in Kotlin with Jetpack Compose, uses SQLite for the move journal, and uses Android's Storage Access Framework (SAF) for all selected-folder access. It does not share the desktop application's Python or PySide6 code.

### Included in the first Android build

- Scan a user-selected phone-storage or SD-card folder recursively without changing it.
- Classify common images, videos, documents, audio, archives, code, installers, and other files using signatures, extensions, and local MIME metadata.
- Calculate SHA-256 hashes, report exact duplicate groups, find empty leaf directories, and flag files at least 500 MiB.
- Detect common code project markers and represent a nested project as one complete folder proposal. If the selected root itself looks like a project, keep all of its contents together.
- Optionally download the 5,148,096-byte EfficientNet-Lite0 ONNX image model, verify its SHA-256 digest, and classify images locally on the CPU.
- Review and switch individual proposed moves on a touch-sized list before confirming them.
- Recheck source hashes immediately before an approved move, avoid name collisions, journal completed moves in SQLite, and undo the latest move group when files are still available.
- Keep the move journal and downloaded model in app-private storage. Scan results stay in app memory. No account, analytics, cloud sync, or remote inference is used.

### Not included yet

- Semantic analysis of video frames, document content, OCR, faces, or arbitrary user-defined concepts.
- File watching, duplicate deletion, empty-folder deletion, user-editable destinations, learned placement examples, journal crash recovery, and user-configurable thresholds.
- Signed production builds, Play Store listing, purchase/licensing flows, and a release update pipeline.

## Orientation and layout

The activity does not request a fixed orientation. Compose reads the current app-window width with `BoxWithConstraints`, so the layout changes based on the actual usable window rather than a phone/tablet label:

| Window | Layout |
| --- | --- |
| Under 780 dp wide | Single-column content, two-by-two metric cards, compact file cards, pinned move controls, and bottom navigation. |
| 780 dp and wider | Side navigation, four metric cards in one row, source and proposed paths side-by-side, and wider action controls. |

The same width-driven layout handles phone rotation, split-screen, foldables, tablets, and desktop-style Android windows. The selected folder, current scan results, and active page remain in the ViewModel across ordinary configuration changes. The app uses system window insets and scrollable content so the short height of landscape phones remains usable.

## Storage permissions and local-only boundary

The user grants access with Android's `ACTION_OPEN_DOCUMENT_TREE` folder picker. Xortify takes persistable read/write access only to the returned tree and does not request broad storage access. The Android build accepts the built-in external-storage document provider, which covers shared phone storage and SD cards. Cloud document providers are rejected so scan and move operations stay local.

Android 11 and later restrict the folder picker from granting a tree for the storage-volume root, `Download`, `Android/data`, and `Android/obb`. Users can choose a permitted subfolder, such as `Documents`, `Pictures`, or a folder they created. SAF providers can differ in their support for moves. File moves fall back to copy, hash verification, and source removal only after the copy passes its checksum. Whole project folders use Android's document-move operation; when a provider cannot perform that safely, Xortify leaves the project in place.

The only network path in the app is the explicit image-model download over HTTPS. Xortify sends no photos, names, hashes, folder paths, or scan results. Model weights are saved in the app's private files area and need to be downloaded again if app data is cleared or the app is removed.

## Scan and organization flow

1. Select a local folder using the system picker.
2. Scan directory metadata and file headers; hash each readable file with SHA-256. The scan is read-only.
3. If the model has been downloaded, run one-image-at-a-time inference for loose image files. Images inside recognized project folders are not moved separately.
4. Propose category folders, topic folders for recognized images, and `Projects/<project name>` for recognized nested project directories. Items already at their proposed path are omitted.
5. Let the user switch off suggestions and confirm the selected move set.
6. Recheck each file hash or complete project-tree fingerprint. Resolve occupied names to a numbered alternative. Move and verify each item, recording the operation in the app's private SQLite database.
7. Undo the latest completed group in reverse order. If the original name is occupied, restore to a numbered alternative instead of overwriting.

No scan result triggers deletion. Exact duplicates, large files, and empty folders are findings only.

## Architecture

~~~text
android/
  app/src/main/java/com/xortify/app/
    MainActivity.kt       Compose host and system folder-picker contract
    XortifyUi.kt          Frutiger Aero styling and adaptive screens
    XortifyViewModel.kt   UI state and background work orchestration
    Models.kt             Scan, plan, duplicate, and view-state models
    FileClassifier.kt     Header, extension, MIME, and project-marker rules
    SafOrganizer.kt       SAF scan, hashing, plan, move verification, and undo
    MoveJournal.kt        SQLite move history and operation state
    LocalVision.kt        Verified model download and CPU ONNX inference
  app/src/main/assets/
    imagenet_labels.txt
~~~

Slow hashing, model download, image inference, and moves run away from the UI thread. A ViewModel keeps the active screen state across rotation. The journal lives in the app-private SQLite database `xortify-android.sqlite3`; it is separate from the selected folder.

## Build

Requirements: Android SDK platform 36, Android build tools 36.0.0, Java 17 or newer, and the SDK license accepted by the person using the SDK. This project pins Gradle 8.13, Android Gradle Plugin 8.13.2, Kotlin 2.2.21, Compose BOM 2025.11.00, and ONNX Runtime Android 1.23.2.

~~~powershell
cd "$env:USERPROFILE\OneDrive\Desktop\Xortify\android"
.\gradlew.bat assembleDebug
~~~

Output: `app/build/outputs/apk/debug/app-debug.apk`. The Android Gradle Plugin signs this debug variant for local installation. A distributable release needs a user-owned release key, a signing configuration, release validation on physical Android devices, and current third-party license review.

## Local image classifier

The classifier is the same fixed-label model used by the desktop prototype. It recognizes 1,000 ImageNet classes and maps supported labels to broad folders such as Cats, Dogs, Birds, Animals, Food, Vehicles, Nature, and Sports. Photos are EXIF-oriented, center-cropped, and resized to 224 × 224. ONNX Runtime executes on the phone CPU. The image model is not a conversational language model and cannot understand custom labels or arbitrary scenes.

The 5 MiB model weights are not bundled in the APK. The optional model download stays an explicit button, and the app checks both the known file length and SHA-256 before loading it. The training-data commercial-use concern recorded in `THIRD_PARTY_NOTICES.md` applies to Android too.
