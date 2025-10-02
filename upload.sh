#!/bin/bash
# Build script for fastrict package

set -e

echo "🔧 Uploading fastrict package..."

python -m twine check dist/*
python -m twine upload --skip-existing dist/*
echo "✅ Package uploaded successfully!"