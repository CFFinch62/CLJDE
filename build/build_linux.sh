#!/bin/bash
# CLJDE build script for Linux.
# Installs deps from pyproject.toml, runs PyInstaller, outputs dist/CLJDE.
#
# Usage: ./build/build_linux.sh
# Output: dist/CLJDE  (standalone executable, no Python required)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "=== CLJDE Build Script ==="
echo "Project: $PROJECT_DIR"
echo ""

# Require Python 3.11+
if ! command -v python3 &>/dev/null; then
    echo "ERROR: python3 not found" >&2
    exit 1
fi
PYTHON_VERSION=$(python3 -c "import sys; print('.'.join(map(str,sys.version_info[:3])))")
echo "Python: $PYTHON_VERSION"

# Create venv if absent
VENV="$PROJECT_DIR/.venv"
if [ ! -d "$VENV" ]; then
    echo "Creating virtual environment..."
    python3 -m venv "$VENV"
fi

# shellcheck disable=SC1091
source "$VENV/bin/activate"
echo "Activated: $VIRTUAL_ENV"

# Install project + build tools
echo "Installing dependencies..."
pip install --upgrade pip setuptools wheel --quiet
pip install --quiet -e "$PROJECT_DIR"
pip install --quiet pyinstaller

# Run PyInstaller via the spec file for reproducible builds
echo "Running PyInstaller..."
cd "$PROJECT_DIR"
pyinstaller build/CLJDE.spec \
    --distpath dist \
    --workpath build/pyinstaller-work \
    --noconfirm

echo ""
echo "=== Build complete ==="
echo "Executable: $PROJECT_DIR/dist/CLJDE"
echo ""
echo "Smoke test (same user):  ./dist/CLJDE"
echo "Portability test:        cp dist/CLJDE ~/CLJDE && ~/CLJDE"
