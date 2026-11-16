$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot

$python = Join-Path $projectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) {
    throw "Create the project's .venv and install the build extra first."
}

$originalPath = $env:Path
try {
    # Avoid collecting the host application's ICU build, which exports a different ABI.
    $env:Path = (($originalPath -split ';') | Where-Object {
        $_ -notmatch '[\\/]poppler[\\/]Library[\\/]bin$'
    }) -join ';'

    & $python -m PyInstaller `
        --noconfirm `
        --clean `
        --onefile `
        --windowed `
        --name Xortify `
        --paths src `
        --collect-data xortify `
        --distpath dist `
        --workpath build `
        --specpath packaging `
        packaging\launcher.py
} finally {
    $env:Path = $originalPath
}

Write-Host "Built $projectRoot\dist\Xortify.exe"
