#!/bin/bash
# Upload script for fastrict package

set -e

echo "🔧 Uploading fastrict package..."

# Check if TWINE_PASSWORD environment variable is set
if [ -z "$TWINE_PASSWORD" ]; then
    echo "⚠️  Warning: TWINE_PASSWORD environment variable is not set."
    echo "   You may be prompted for your PyPI token during upload."
fi

# Verify package integrity
echo "📋 Checking package integrity..."
python -m twine check dist/*

# Upload to PyPI (skip existing versions)
echo "📤 Uploading to PyPI..."
python -m twine upload --skip-existing dist/*

echo "✅ Package uploaded successfully!"
echo "🔗 Check your package at: https://pypi.org/project/fastrict/"