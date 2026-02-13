#!/usr/bin/env sh
set -e

uv run uvicorn soupnotify.app.main:app --host 0.0.0.0 --port 8000 &
uv run python -m soupnotify.bot
