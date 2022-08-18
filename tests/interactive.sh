#!/usr/bin/env bash
set -e
PROJECTDIR=$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." && pwd )

main() {
  if [[ -n $1 ]]; then
    if [[ $1 == '--help' ]]; then
      printf "Run the docopt.completion working copy code interactively\n"
      printf " Usage: interactive [shell]\n"
      exit 0
    else
      if [[ $# -gt 1 ]]; then
        printf "only one SHELL argument allowed\n" >&2
        exit 64 # 64=$EX_USAGE
      fi
      _shell=$1
    fi
  fi

  if [[ -z $_shell ]]; then
    _shell=$SHELL
  fi

  _TMPDIR="$(mktemp -d --suffix '-docopt.completions')"
  _HOME="$_TMPDIR/home"
  _PATH="$PATH:$PROJECTDIR/tests/interactive/programs"
  mkdir "$_HOME"
  (shopt -s dotglob && cp "$PROJECTDIR/tests/interactive/home"/* "$_HOME")

  /usr/bin/env -i -C "$_HOME" \
    HOME="$_HOME" PATH="$_PATH" PROJECTDIR="$PROJECTDIR" \
    TERM="$TERM" \
    "$_shell"
  rm -rf "$_TMPDIR"
}


main "$@"
