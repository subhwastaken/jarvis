#!/bin/bash
set -e

# Prevent macOS AppleDouble shadow files
export COPYFILE_DISABLE=1

echo "⚡ Starting NIKO Desktop Assistant..."

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$REPO_DIR"

# Clean any macOS metadata shadow files
find . -name "._*" -delete 2>/dev/null || true
find . -name ".DS_Store" -delete 2>/dev/null || true

# Validate Python 3
if ! command -v python3 >/dev/null 2>&1; then
    echo "❌ Python 3.10+ is required. Please install Python from https://www.python.org or via Homebrew: brew install python"
    exit 1
fi

# Set up local virtual environment if not present
if [ ! -f ".venv/bin/python" ]; then
    echo "📦 Creating virtual environment in .venv..."
    python3 -m venv .venv
    echo "📥 Installing dependencies from requirements.txt..."
    .venv/bin/pip install -q --upgrade pip
    .venv/bin/pip install -q -r requirements.txt
fi


# Launch NIKO
if [ $# -eq 0 ]; then
    echo "🚀 Launching NIKO Dynamic Island HUD..."
    exec .venv/bin/python siri.py --ui
else
    exec .venv/bin/python siri.py "$@"
fi
