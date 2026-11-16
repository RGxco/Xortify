# Xortify

Xortify scans a folder and suggests where to sort its files. Review the suggestions before anything is moved.

The Windows desktop app and Android companion work with folders you choose. Scanning does not change files.

## What it does

- Sorts common file types into folders such as Images, Videos, Documents, Audio, Archives, Code, Installers, and Other.
- Offers optional photo grouping for some familiar subjects. It needs a separate download, and you can review its suggestions.
- Keeps recognized code projects together as complete folders.
- Finds exact duplicates, large files, and empty folders. It does not delete them.
- Lets you select files and change proposed destinations before moving.
- Records approved moves so you can undo them.

Xortify does not upload selected files or scan results. The optional photo grouping download is fetched separately when requested. See [third-party notices](docs/THIRD_PARTY_NOTICES.md) for component details.

## Download

Get the Windows app and Android preview APK from [GitHub Releases](https://github.com/RGxco/Xortify/releases).

The Android APK is a debug-signed preview for Android 8.0 and newer. It is for direct installation and is not a Play Store release.

## Run on Windows

Use 64-bit Python 3.10 or newer:

~~~powershell
cd "$env:USERPROFILE/OneDrive/Desktop/Xortify"
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev,vision]"
python -m xortify
~~~

The optional photo grouping feature needs the vision dependencies and a one-time download from inside the app.

## Build the Windows app

~~~powershell
python -m pip install -e ".[dev,vision,build]"
powershell -ExecutionPolicy Bypass -File ./packaging/build_windows.ps1
~~~

The executable is written to dist/Xortify.exe.

## Build the Android app

Open the android folder in Android Studio, or build the debug APK from PowerShell after setting up the Android SDK:

~~~powershell
cd "$env:USERPROFILE/OneDrive/Desktop/Xortify/android"
.\gradlew.bat assembleDebug
~~~

The APK is written to android/app/build/outputs/apk/debug/app-debug.apk. A signed production build needs a release key and additional release preparation.

The app uses Android's folder picker, supports portrait and landscape, and works with a folder you choose on phone storage or an SD card. Android may restrict access to some folders, including storage roots and Downloads.

## Local data

- Scan history and move records are stored on your device.
- Selected files, filenames, and scan results are not uploaded.
- The optional photo grouping download requires an internet connection when first installed; it is used on the device afterward.

For implementation details, see the [technical specification](docs/TECHNICAL_SPEC.md), [Android notes](docs/ANDROID_SPEC.md), and [product roadmap](docs/PRODUCT_AND_REVENUE_ROADMAP.md).
