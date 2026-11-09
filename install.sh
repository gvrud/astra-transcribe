#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WITH_MODEL=1

for argument in "$@"; do
    case "$argument" in
        --with-model)
            WITH_MODEL=1
            ;;
        --no-model)
            WITH_MODEL=0
            ;;
        -h|--help)
            printf 'Использование: %s [--with-model|--no-model]\n' "$0"
            exit 0
            ;;
        *)
            printf 'Неизвестный параметр: %s\n' "$argument" >&2
            exit 2
            ;;
    esac
done

PYTHON="${PYTHON:-python3}"

if ! command -v "$PYTHON" >/dev/null 2>&1; then
    printf 'Не найден Python 3.\n' >&2
    exit 1
fi

if ! "$PYTHON" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 9) else 1)'; then
    printf 'Требуется Python 3.9 или новее.\n' >&2
    exit 1
fi

if ! "$PYTHON" -c 'import PyQt5.QtWidgets' >/dev/null 2>&1; then
    printf 'Не найден PyQt5. Установите пакет: sudo apt install python3-pyqt5\n' >&2
    exit 1
fi

if [ ! -d "$ROOT/.venv" ]; then
    "$PYTHON" -m venv --system-site-packages "$ROOT/.venv"
fi

"$ROOT/.venv/bin/python" -m pip install --disable-pip-version-check -r "$ROOT/requirements.txt"
"$ROOT/.venv/bin/python" -m pip install --disable-pip-version-check -e "$ROOT"

mkdir -p "$HOME/.local/bin"
mkdir -p "$HOME/.local/share/applications"
mkdir -p "$HOME/.local/share/icons/hicolor/scalable/apps"

ln -sf "$ROOT/bin/astra-transcribe" "$HOME/.local/bin/astra-transcribe"
ln -sf "$ROOT/bin/astra-transcribe-cli" "$HOME/.local/bin/astra-transcribe-cli"

sed \
    -e "s|@EXEC@|$HOME/.local/bin/astra-transcribe|g" \
    -e "s|@ICON@|astra-transcribe|g" \
    "$ROOT/share/astra-transcribe.desktop.in" \
    > "$HOME/.local/share/applications/astra-transcribe.desktop"

cp "$ROOT/src/multitool_transcriber/assets/astra-transcribe.svg" \
    "$HOME/.local/share/icons/hicolor/scalable/apps/astra-transcribe.svg"

if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$HOME/.local/share/applications" >/dev/null 2>&1 || true
fi

if [ "$WITH_MODEL" = "1" ]; then
    if ! "$ROOT/.venv/bin/python" - <<'PY'
from multitool_transcriber.models import discover_models

raise SystemExit(0 if discover_models() else 1)
PY
    then
        "$ROOT/.venv/bin/python" -m multitool_transcriber.cli --download-model vosk-model-small-ru-0.22
    fi
fi

printf '\nГотово.\n'
printf 'Запуск из меню: Astra Transcribe\n'
printf 'Запуск из терминала: %s/.local/bin/astra-transcribe\n' "$HOME"
printf 'Командная строка: %s/.local/bin/astra-transcribe-cli --help\n' "$HOME"
