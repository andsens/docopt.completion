#!/usr/bin/env zsh

mkdir -p "$HOME/.zfunc"
naval_fate --help | "$PROJECTDIR/.venv/bin/docopt-completion" zsh > "$HOME/.zfunc/_naval_fate"
fpath=("$HOME/.zfunc" $fpath)
autoload -U compinit
compinit
