#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VERSION="$(sed -n 's/^__version__ = "\(.*\)"$/\1/p' "$ROOT/src/multitool_transcriber/__init__.py" | head -n 1)"
if [ -z "$VERSION" ]; then
    VERSION="1.0.3"
fi

PYTHON_VERSION="3.11.18"
PBS_RELEASE="20261026"
PYQT5_VERSION="5.15.9"
PYTHON_URL="https://github.com/astral-sh/python-build-standalone/releases/download/${PBS_RELEASE}/cpython-${PYTHON_VERSION}+${PBS_RELEASE}-x86_64-unknown-linux-gnu-install_only.tar.gz"
APPIMAGETOOL_URL="https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage"
RUNTIME_URL="https://github.com/AppImage/type2-runtime/releases/download/continuous/runtime-x86_64"

BUILD="$ROOT/.build/appimage"
CACHE="$ROOT/.build/cache"
APPDIR="$BUILD/AppDir"
DIST="$ROOT/dist"
OUTPUT="$DIST/AstraTranscribe-${VERSION}-x86_64.AppImage"

fetch() {
    local url="$1"
    local destination="$2"
    if [ -s "$destination" ]; then
        return
    fi
    mkdir -p "$(dirname "$destination")"
    printf 'Загрузка %s\n' "$url"
    curl -L --fail --silent --show-error -o "$destination.part" "$url"
    mv "$destination.part" "$destination"
}

rm -rf "$BUILD"
mkdir -p "$APPDIR/usr" "$CACHE" "$DIST"

fetch "$PYTHON_URL" "$CACHE/python.tar.gz"
tar -xzf "$CACHE/python.tar.gz" -C "$APPDIR/usr" --strip-components=1

PYTHON="$APPDIR/usr/bin/python3"
SITE="$APPDIR/usr/lib/python3.11/site-packages"

"$PYTHON" -m pip install --disable-pip-version-check --no-warn-script-location \
    -r "$ROOT/requirements.txt" "PyQt5==$PYQT5_VERSION"

cp -a "$ROOT/src/multitool_transcriber" "$SITE/"
find "$SITE/multitool_transcriber" -type d -name __pycache__ -prune -exec rm -rf {} +

MODEL_NAME="vosk-model-small-ru-0.22"
MODEL_PATH="$("$PYTHON" - <<'PY'
from multitool_transcriber.models import find_installed

model = find_installed("vosk-model-small-ru-0.22")
print(model or "")
PY
)"
if [ -z "$MODEL_PATH" ]; then
    "$PYTHON" -m multitool_transcriber.cli --download-model "$MODEL_NAME"
    MODEL_PATH="$("$PYTHON" - <<'PY'
from multitool_transcriber.models import find_installed

model = find_installed("vosk-model-small-ru-0.22")
print(model or "")
PY
)"
fi
mkdir -p "$APPDIR/usr/share/astra-transcribe/models"
cp -a "$MODEL_PATH" "$APPDIR/usr/share/astra-transcribe/models/"

cp "$ROOT/appimage/AppRun" "$APPDIR/AppRun"
chmod +x "$APPDIR/AppRun"
cp "$ROOT/appimage/astra-transcribe.desktop" "$APPDIR/astra-transcribe.desktop"
mkdir -p "$APPDIR/usr/share/applications"
mkdir -p "$APPDIR/usr/share/icons/hicolor/scalable/apps"
cp "$ROOT/appimage/astra-transcribe.desktop" "$APPDIR/usr/share/applications/astra-transcribe.desktop"
cp "$ROOT/src/multitool_transcriber/assets/astra-transcribe.svg" "$APPDIR/astra-transcribe.svg"
cp "$ROOT/src/multitool_transcriber/assets/astra-transcribe.png" "$APPDIR/astra-transcribe.png"
mkdir -p "$APPDIR/usr/share/icons/hicolor/scalable/apps"
mkdir -p "$APPDIR/usr/share/icons/hicolor/256x256/apps"
cp "$ROOT/src/multitool_transcriber/assets/astra-transcribe.svg" "$APPDIR/usr/share/icons/hicolor/scalable/apps/astra-transcribe.svg"
cp "$ROOT/src/multitool_transcriber/assets/astra-transcribe.png" "$APPDIR/usr/share/icons/hicolor/256x256/apps/astra-transcribe.png"

find "$APPDIR" -type d -name __pycache__ -prune -exec rm -rf {} +
find "$APPDIR" -type f -name '*.pyc' -delete

fetch "$APPIMAGETOOL_URL" "$CACHE/appimagetool"
chmod +x "$CACHE/appimagetool"
if [ ! -x "$CACHE/appimagetool-squashfs/AppRun" ]; then
    rm -rf "$CACHE/squashfs-root"
    (cd "$CACHE" && "$CACHE/appimagetool" --appimage-extract >/dev/null)
    rm -rf "$CACHE/appimagetool-squashfs"
    mv "$CACHE/squashfs-root" "$CACHE/appimagetool-squashfs"
fi

fetch "$RUNTIME_URL" "$CACHE/runtime-x86_64"

rm -f "$OUTPUT"
ARCH=x86_64 "$CACHE/appimagetool-squashfs/AppRun" --no-appstream \
    --runtime-file "$CACHE/runtime-x86_64" "$APPDIR" "$OUTPUT"

APPIMAGE_EXTRACT_AND_RUN=1 QT_QPA_PLATFORM=offscreen "$OUTPUT" --cli --help >/dev/null 2>"$BUILD/smoke.log"

printf '\nГотово: %s\n' "$OUTPUT"
ls -lh "$OUTPUT"
(cd "$DIST" && sha256sum "$(basename "$OUTPUT")" > "$(basename "$OUTPUT").sha256")
cat "$OUTPUT.sha256"
