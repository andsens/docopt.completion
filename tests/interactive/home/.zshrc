#!/usr/bin/env zsh

fpath=($PROJECTDIR/tests/interactive/completions/zsh.d $fpath)
autoload -U compinit
compinit
