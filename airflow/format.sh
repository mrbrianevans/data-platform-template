#!/bin/sh
# Format Python with the project's ruff. `uv format` is experimental and
# downloads its own ruff, so use this instead: `uv run ./format.sh`.
cd "$(dirname "$0")" || exit 1
exec uv run ruff format "$@"
