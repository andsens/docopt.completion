import re
import shlex
from docopt_completion import tables as Tb, script

compgen = {
  'files': 'compopt -o filenames; mapfile -t -O "${#values[@]}" values < <(compgen -f -- "$2")',
  'dirs': 'compopt -o filenames; mapfile -t -O "${#values[@]}" values < <(compgen -d -- "$2")',
  'hosts': 'mapfile -t -O "${#values[@]}" values < <(compgen -A hostname -- "$2")',
  'users': 'mapfile -t -O "${#values[@]}" values < <(compgen -u -- "$2")',
  'groups': 'mapfile -t -O "${#values[@]}" values < <(compgen -g -- "$2")',
  'commands': 'mapfile -t -O "${#values[@]}" values < <(compgen -c -- "$2")',
  'signals': 'mapfile -t -O "${#values[@]}" values < <(compgen -A signal -- "$2")',
  'processes': 'mapfile -t -O "${#values[@]}" values < <(compgen -W "$(ps -e -o pid=)" -- "$2")',
}


def source_code(source: Tb.Source) -> str:
  if isinstance(source, str):
    return compgen[source]
  if 'words' in source:
    words = ' '.join(shlex.quote(str(word)) for word in source['words'])
    return f'local candidates=({words}); for w in "${{candidates[@]}}"; do [[ $w = "$2"* ]] && values+=("$w"); done'
  return f'while IFS= read -r w; do [[ $w = "$2"* ]] && values+=("$w"); done < <({source["command"]})'


def generate(prog: str, compiled: Tb.Tables, refresh: "script.Refresh | None" = None) -> str:
  function = '_docopt_' + re.sub(r'[^A-Za-z0-9_]', '_', prog)
  code = ''
  if refresh is not None:
    if isinstance(refresh, str):
      # BASH_SOURCE[0] is the file the function was defined in
      setup = f'local script=${{BASH_SOURCE[0]}} bin\nbin=${{script%/*}}/{script.quote(refresh)}'
      check = '[[ -e $bin && ( $bin -nt $script || $bin -ot $script ) ]]'
      regenerate, path = 'docopt.completion register --dir="${script%/*}" bash "$bin"', '"$script"'
    else:
      binary, path, regenerate = (script.quote(refresh[0]), script.quote(refresh[1]), shlex.join(refresh[2]))
      setup = 'local bin'
      check = (f'bin=$(type -P {shlex.quote(prog)}) && bin=$(realpath -- "$bin") \\\n'
               f'  && [[ $bin != {binary} || $bin -nt {path} || $bin -ot {path} ]]')
    code = f'''# Regenerate this script when {prog} changed since
{setup}
if [[ -z ${{_docopt_refreshed-}} ]] && {check}; then
  local _docopt_refreshed=1
  if {regenerate} >/dev/null 2>&1; then
    # shellcheck disable=SC1090
    source {path}
    {function} "$@"
    return
  fi
fi'''
  return script.render('bash.sh', prog, function, compiled, source_code, 0, False, code)
