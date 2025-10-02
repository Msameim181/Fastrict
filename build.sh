#!/bin/bash
# Build script for fastrict package

set -e

echo "🔧 Building fastrict package..."

# Clean previous builds
rm -rf build/ dist/ *.egg-info/

# Install build dependencies
pip install --upgrade pip setuptools wheel build twine

# Build the package
python -m build

echo "✅ Package built successfully!"
echo "📦 Files created:"
ls -la dist/

echo ""
echo "🚀 To install locally:"
echo "pip install dist/fastrict-1.0.0-py3-none-any.whl"
echo ""
echo "📤 To upload to PyPI:"
echo "twine upload dist/*"