#!/usr/bin/env bash
# =============================================================================
# build.sh — MTG Sim build script (Linux / macOS)
#
# Usage:
#   ./build.sh              # standard build
#   ./build.sh --onefile    # single executable (larger, slower to start)
#   ./build.sh --clean      # remove build artifacts and exit
#   ./build.sh --help
#
# Output: dist/mtg_sim/mtg_sim  (or dist/mtg_sim with --onefile)
# Requires: Python 3.10+, pip
# =============================================================================

set -euo pipefail

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
APP_NAME="mtg_sim"
ENTRY_POINT="main.py"
VENV_DIR=".venv"
DIST_DIR="dist"
BUILD_DIR="build"
ONEFILE=0
CLEAN_ONLY=0

# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------
for arg in "$@"; do
  case $arg in
    --onefile) ONEFILE=1 ;;
    --clean)   CLEAN_ONLY=1 ;;
    --help)
      echo "Usage: $0 [--onefile] [--clean] [--help]"
      echo ""
      echo "  --onefile   Bundle into a single executable file (slower startup)"
      echo "  --clean     Remove build/dist artifacts and exit"
      echo "  --help      Show this message"
      exit 0
      ;;
    *)
      echo "Unknown argument: $arg  (use --help for usage)"
      exit 1
      ;;
  esac
done

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
log()  { echo "[build] $*"; }
warn() { echo "[build] WARNING: $*" >&2; }
die()  { echo "[build] ERROR: $*" >&2; exit 1; }

# ---------------------------------------------------------------------------
# Clean
# ---------------------------------------------------------------------------
if [ "$CLEAN_ONLY" -eq 1 ]; then
  log "Cleaning build artifacts..."
  rm -rf "$BUILD_DIR" "$DIST_DIR" "${APP_NAME}.spec"
  log "Done."
  exit 0
fi

# ---------------------------------------------------------------------------
# Sanity checks
# ---------------------------------------------------------------------------
log "Checking Python..."
PYTHON=$(command -v python3 || command -v python || die "Python not found. Install Python 3.10+.")
PY_VERSION=$("$PYTHON" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
PY_MAJOR=$("$PYTHON" -c "import sys; print(sys.version_info.major)")
PY_MINOR=$("$PYTHON" -c "import sys; print(sys.version_info.minor)")

if [ "$PY_MAJOR" -lt 3 ] || { [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 10 ]; }; then
  die "Python 3.10+ required (found $PY_VERSION)."
fi
log "  Python $PY_VERSION — OK"

# ---------------------------------------------------------------------------
# Virtual environment
# ---------------------------------------------------------------------------
if [ ! -d "$VENV_DIR" ]; then
  log "Creating virtual environment in $VENV_DIR..."
  "$PYTHON" -m venv "$VENV_DIR"
fi

# Activate
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"
PIP="$VENV_DIR/bin/pip"
PYINSTALLER="$VENV_DIR/bin/pyinstaller"

log "Upgrading pip..."
"$PIP" install --upgrade pip --quiet

# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------
log "Installing dependencies..."
if [ -f "requirements.txt" ]; then
  "$PIP" install -r requirements.txt --quiet
  log "  Installed from requirements.txt"
else
  warn "No requirements.txt found — installing PyInstaller only."
fi
"$PIP" install pyinstaller pytest --quiet
log "  PyInstaller + pytest ready"

# Make the project importable inside the venv so both pytest and PyInstaller
# can resolve mtg_sim.* without a setup.py / pyproject.toml.
# A .pth file in site-packages adds the project root to sys.path at startup.
if [ -f "setup.py" ] || [ -f "pyproject.toml" ]; then
  "$PIP" install -e . --quiet
  log "  Project installed (editable mode)"
else
  SITE_PACKAGES=$("$VENV_DIR/bin/python" -c "import site; print(site.getsitepackages()[0])")
  echo "$(pwd)" > "$SITE_PACKAGES/mtg_sim_dev.pth"
  log "  Project root added to venv path via mtg_sim_dev.pth"
fi

# ---------------------------------------------------------------------------
# Entrypoint check
# ---------------------------------------------------------------------------
if [ ! -f "$ENTRY_POINT" ]; then
  warn "$ENTRY_POINT not found — creating a temporary stub."
  warn "Replace this with your real entrypoint before distributing."
  cat > "$ENTRY_POINT" << 'STUB'
"""
Temporary entrypoint stub.
Replace with the real TUI entrypoint once the UI is implemented.
"""
import sys
# Force-import the engine so PyInstaller can trace the dependency graph.
import mtg_sim.engine  # noqa: F401
print("MTG Sim — engine loaded successfully.")
print("TUI not yet implemented. Run tests with: python -m pytest mtg_sim/tests/")
sys.exit(0)
STUB
  STUB_CREATED=1
else
  STUB_CREATED=0
fi

# ---------------------------------------------------------------------------
# Run tests before building
# ---------------------------------------------------------------------------
log "Running tests..."
if ! "$VENV_DIR/bin/python" -m pytest mtg_sim/tests/ -q; then
  [ "$STUB_CREATED" -eq 1 ] && rm -f "$ENTRY_POINT"
  die "Tests failed — fix errors before building."
fi
log "  All tests passed."

# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------
# Tell PyInstaller where to find the project source so hidden imports resolve.
PROJECT_ROOT="$(pwd)"

PYINSTALLER_ARGS=(
  --name "$APP_NAME"
  --distpath "$DIST_DIR"
  --workpath "$BUILD_DIR"
  --paths "$PROJECT_ROOT"
  --noconfirm
  --clean
)

if [ "$ONEFILE" -eq 1 ]; then
  PYINSTALLER_ARGS+=(--onefile)
  log "Build mode: single file"
else
  PYINSTALLER_ARGS+=(--onedir)
  log "Build mode: directory (use --onefile for a single executable)"
fi

# Bundle the package source as data so it's available at runtime
[ -d "mtg_sim" ]          && PYINSTALLER_ARGS+=("--add-data=mtg_sim:mtg_sim")
[ -f "config.ini" ]       && PYINSTALLER_ARGS+=("--add-data=config.ini:.")
[ -f "requirements.txt" ] && PYINSTALLER_ARGS+=("--add-data=requirements.txt:.")

# Explicit hidden imports (belt-and-suspenders alongside --paths)
PYINSTALLER_ARGS+=(
  --hidden-import=mtg_sim
  --hidden-import=mtg_sim.engine
  --hidden-import=mtg_sim.engine.deck
  --hidden-import=mtg_sim.engine.game_state
  --hidden-import=mtg_sim.engine.simulation
  --hidden-import=mtg_sim.engine.config
  --hidden-import=mtg_sim.engine.app_state
)

log "Running PyInstaller..."
"$PYINSTALLER" "${PYINSTALLER_ARGS[@]}" "$ENTRY_POINT"

# ---------------------------------------------------------------------------
# Cleanup stub if we created it
# ---------------------------------------------------------------------------
if [ "$STUB_CREATED" -eq 1 ]; then
  rm -f "$ENTRY_POINT"
fi

# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------
if [ "$ONEFILE" -eq 1 ]; then
  OUTPUT="$DIST_DIR/$APP_NAME"
else
  OUTPUT="$DIST_DIR/$APP_NAME/$APP_NAME"
fi

echo ""
log "Build complete!"
log "  Output: $OUTPUT"
log ""
log "To run:"
if [ "$ONEFILE" -eq 1 ]; then
  log "  ./$DIST_DIR/$APP_NAME"
else
  log "  ./$DIST_DIR/$APP_NAME/$APP_NAME"
fi
log ""
log "To clean up:  $0 --clean"