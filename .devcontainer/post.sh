#!/usr/bin/env bash
set -e

# The tests drive interactive bash and zsh sessions
command -v zsh >/dev/null || { sudo apt-get update -q && sudo apt-get install -qy zsh; }
pip --disable-pip-version-check --no-cache-dir install --user poetry
poetry install --no-root
