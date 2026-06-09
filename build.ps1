# =============================================================================
# build.ps1 — MTG Sim build script (Windows)
#
# Usage:
#   .\build.ps1              # standard build
#   .\build.ps1 -OneFile     # single executable (larger, slower to start)
#   .\build.ps1 -Clean       # remove build artifacts and exit
#   .\build.ps1 -Help
#
# Output: dist\mtg_sim\mtg_sim.exe  (or dist\mtg_sim.exe with -OneFile)
# Requires: Python 3.10+, pip
#
# If you get "cannot be loaded because running scripts is disabled", run:
#   Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
# =============================================================================

param(
    [switch]$OneFile,
    [switch]$Clean,
    [switch]$Help
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
$AppName    = "mtg_sim"
$EntryPoint = "main.py"
$VenvDir    = ".venv"
$DistDir    = "dist"
$BuildDir   = "build"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
function Log  { param($msg) Write-Host "[build] $msg" -ForegroundColor Cyan }
function Warn { param($msg) Write-Host "[build] WARNING: $msg" -ForegroundColor Yellow }
function Die  { param($msg) Write-Host "[build] ERROR: $msg" -ForegroundColor Red; exit 1 }

# ---------------------------------------------------------------------------
# Help
# ---------------------------------------------------------------------------
if ($Help) {
    Write-Host @"
Usage: .\build.ps1 [options]

  -OneFile    Bundle into a single .exe file (slower startup)
  -Clean      Remove build/dist artifacts and exit
  -Help       Show this message

Output: dist\$AppName\$AppName.exe   (default)
        dist\$AppName.exe            (with -OneFile)
"@
    exit 0
}

# ---------------------------------------------------------------------------
# Clean
# ---------------------------------------------------------------------------
if ($Clean) {
    Log "Cleaning build artifacts..."
    foreach ($dir in @($BuildDir, $DistDir)) {
        if (Test-Path $dir) { Remove-Item $dir -Recurse -Force }
    }
    if (Test-Path "$AppName.spec") { Remove-Item "$AppName.spec" -Force }
    Log "Done."
    exit 0
}

# ---------------------------------------------------------------------------
# Sanity checks
# ---------------------------------------------------------------------------
Log "Checking Python..."
$PythonCmd = $null
foreach ($candidate in @("python", "python3", "py")) {
    if (Get-Command $candidate -ErrorAction SilentlyContinue) {
        $PythonCmd = $candidate
        break
    }
}
if (-not $PythonCmd) {
    Die "Python not found. Install Python 3.10+ from https://python.org and ensure it's on PATH."
}

$PyVersion = & $PythonCmd -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
$PyMajor   = & $PythonCmd -c "import sys; print(sys.version_info.major)"
$PyMinor   = & $PythonCmd -c "import sys; print(sys.version_info.minor)"

if ([int]$PyMajor -lt 3 -or ([int]$PyMajor -eq 3 -and [int]$PyMinor -lt 10)) {
    Die "Python 3.10+ required (found $PyVersion)."
}
Log "  Python $PyVersion — OK"

# ---------------------------------------------------------------------------
# Virtual environment
# ---------------------------------------------------------------------------
if (-not (Test-Path $VenvDir)) {
    Log "Creating virtual environment in $VenvDir..."
    & $PythonCmd -m venv $VenvDir
}

$Pip          = "$VenvDir\Scripts\pip.exe"
$PyInstaller  = "$VenvDir\Scripts\pyinstaller.exe"
$VenvPython   = "$VenvDir\Scripts\python.exe"
$Pytest       = "$VenvDir\Scripts\pytest.exe"

Log "Upgrading pip..."
& $Pip install --upgrade pip --quiet

# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------
Log "Installing dependencies..."
if (Test-Path "requirements.txt") {
    & $Pip install -r requirements.txt --quiet
    Log "  Installed from requirements.txt"
} else {
    Warn "No requirements.txt found — installing PyInstaller only."
}
& $Pip install pyinstaller --quiet
Log "  PyInstaller ready"

# ---------------------------------------------------------------------------
# Entrypoint check
# ---------------------------------------------------------------------------
$StubCreated = $false
if (-not (Test-Path $EntryPoint)) {
    Warn "$EntryPoint not found — creating a temporary stub."
    Warn "Replace this with your real entrypoint before distributing."
    @'
"""
Temporary entrypoint stub.
Replace with the real TUI entrypoint once the UI is implemented.
"""
import sys
print("MTG Sim -- engine loaded successfully.")
print("TUI not yet implemented. Run the tests with: python -m pytest mtg_sim/tests/")
sys.exit(0)
'@ | Set-Content $EntryPoint -Encoding UTF8
    $StubCreated = $true
}

# ---------------------------------------------------------------------------
# Run tests before building
# ---------------------------------------------------------------------------
if (Test-Path $Pytest) {
    Log "Running tests..."
    & $Pytest mtg_sim/tests/ -q
    if ($LASTEXITCODE -ne 0) {
        if ($StubCreated) { Remove-Item $EntryPoint -Force }
        Die "Tests failed — fix errors before building."
    }
    Log "  All tests passed."
} else {
    Warn "pytest not available in venv — skipping tests."
}

# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------
$PyInstallerArgs = @(
    "--name", $AppName,
    "--distpath", $DistDir,
    "--workpath", $BuildDir,
    "--noconfirm",
    "--clean"
)

if ($OneFile) {
    $PyInstallerArgs += "--onefile"
    Log "Build mode: single file"
} else {
    $PyInstallerArgs += "--onedir"
    Log "Build mode: directory (use -OneFile for a single .exe)"
}

# Add data files if present
if (Test-Path "mtg_sim")         { $PyInstallerArgs += "--add-data=mtg_sim;mtg_sim" }
if (Test-Path "config.ini")      { $PyInstallerArgs += "--add-data=config.ini;." }
if (Test-Path "requirements.txt"){ $PyInstallerArgs += "--add-data=requirements.txt;." }

# Hidden imports
$PyInstallerArgs += @(
    "--hidden-import=mtg_sim.engine",
    "--hidden-import=mtg_sim.engine.deck",
    "--hidden-import=mtg_sim.engine.game_state",
    "--hidden-import=mtg_sim.engine.simulation",
    "--hidden-import=mtg_sim.engine.config",
    "--hidden-import=mtg_sim.engine.app_state"
)

$PyInstallerArgs += $EntryPoint

Log "Running PyInstaller..."
& $PyInstaller @PyInstallerArgs

# ---------------------------------------------------------------------------
# Cleanup stub
# ---------------------------------------------------------------------------
if ($StubCreated) {
    Remove-Item $EntryPoint -Force
}

# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------
if ($OneFile) {
    $Output = "$DistDir\$AppName.exe"
} else {
    $Output = "$DistDir\$AppName\$AppName.exe"
}

Write-Host ""
Log "Build complete!"
Log "  Output: $Output"
Log ""
Log "To run:"
if ($OneFile) {
    Log "  .\$DistDir\$AppName.exe"
} else {
    Log "  .\$DistDir\$AppName\$AppName.exe"
}
Log ""
Log "To clean up:  .\build.ps1 -Clean"