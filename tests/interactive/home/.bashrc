#!/usr/bin/env bash

# shellcheck disable=1090
source <(naval_fate --help | "$PROJECTDIR/.venv/bin/docopt.completion" bash)
