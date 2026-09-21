#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "wallgen — установка в виртуальное окружение"
python3 -m venv .venv
echo "Активируем окружение..."
. .venv/bin/activate
echo "Устанавливаем зависимости..."
pip install -e .
echo ""
echo "Готово! Запустите:"
echo "  source .venv/bin/activate && wallgen"
echo "Или просто:"
echo "  . .venv/bin/activate; wallgen"
