#!/bin/sh
# Lancement de Roue Libre (après installation via install.sh).
cd "$(dirname "$0")"
if [ -f .venv/bin/activate ]; then
    . ./.venv/bin/activate
fi
exec python3 main.py
