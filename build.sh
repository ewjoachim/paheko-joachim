#!/bin/bash
# Build a module archive for Paheko Cloud (uploaded via the admin).
#
# Format expected by Paheko (UserTemplate\Modules::import): the zip contains
#   modules/<name>/module.ini + every module file (subdirectories included).
# <name> must match /^[a-z][a-z0-9]*(_[a-z0-9]+)*$/ and be unique in the zip.
#
# Usage: ./build.sh [module_name]   (default: suivi_cheques)
set -euo pipefail

MODULE="${1:-suivi_cheques}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Modules live in this repo under modules/ (e.g. ./modules/suivi_cheques/).
SRC="$SCRIPT_DIR/modules/$MODULE"
BUILD_DIR="$SCRIPT_DIR/_pkg"
OUTPUT_ZIP="$SCRIPT_DIR/${MODULE}-paheko-cloud.zip"

if [ ! -f "$SRC/module.ini" ]; then
	echo "❌ Module not found or missing module.ini: $SRC" >&2
	exit 1
fi

# Prepare a clean modules/<name>/… tree
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR/modules/$MODULE"

# Copy the module files, excluding anything that is not part of the module.
rsync -a \
	--exclude='.git' \
	--exclude='.DS_Store' \
	--exclude='*.swp' \
	--exclude='build.sh' \
	--exclude='_pkg' \
	"$SRC"/ "$BUILD_DIR/modules/$MODULE/"

# STAGE_ONLY: leave the staged tree ($BUILD_DIR/modules/<name>/…) and skip the zip.
# Used by CI, where actions/upload-artifact re-zips the uploaded directory itself
# (zipping here too would produce a useless zip-inside-a-zip).
if [ -n "${STAGE_ONLY:-}" ]; then
	echo "✅ Staged: $BUILD_DIR/modules/$MODULE"
	exit 0
fi

# Create the zip (paths relative to BUILD_DIR -> modules/<name>/…)
rm -f "$OUTPUT_ZIP"
( cd "$BUILD_DIR" && zip -rq "$OUTPUT_ZIP" modules )
rm -rf "$BUILD_DIR"

if [ -f "$OUTPUT_ZIP" ]; then
	echo "✅ Archive created: $OUTPUT_ZIP ($(du -h "$OUTPUT_ZIP" | cut -f1))"
	echo "   Contents:"
	unzip -l "$OUTPUT_ZIP" | awk 'NR>3 && $4!="" {print "     " $4}'
else
	echo "❌ Failed to create the archive" >&2
	exit 1
fi
