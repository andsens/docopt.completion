import os
import re
import shlex
import typing as T
from docopt_completion import tables as Tb

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


def array(name: str, values: T.Iterable[T.Any]) -> str:
  return f'local {name}=(' + ' '.join(shlex.quote(str(value)) for value in values) + ')'


def generate(prog: str, compiled: Tb.Tables) -> str:
  source_sets: T.List[T.List[Tb.Source]] = []

  def source_set(sources: T.List[Tb.Source]) -> int:
    if not sources:
      return -1
    if sources not in source_sets:
      source_sets.append(sources)
    return source_sets.index(sources)

  def none(index: "int | None") -> int:
    return -1 if index is None else index

  options = compiled.options
  states = compiled.states
  transitions = [(index, name, target) for index, state in enumerate(states)
                 for name, (target, _) in state.commands.items()]
  table_lines = [
    array('opt_names', (' '.join(o.names) for o in options)),
    array('opt_arg', (int(o.argument) for o in options)),
    array('opt_rep', (int(o.repeatable) for o in options)),
    array('opt_src', (source_set(o.complete) for o in options)),
    array('cmd_state', (t[0] for t in transitions)),
    array('cmd_name', (t[1] for t in transitions)),
    array('cmd_next', (t[2] for t in transitions)),
    array('st_sep', (none(s.separator) for s in states)),
    array('st_other', (none(s.other) for s in states)),
    array('st_src', (source_set(s.complete) for s in states)),
    array('st_opts', (' '.join(map(str, s.options)) for s in states)),
  ]
  source_lines: T.List[str] = []
  for index, sources in enumerate(source_sets):
    source_lines.append(f'{index})')
    source_lines += [f'  {source_code(source)}' for source in sources]
    source_lines.append('  ;;')

  with open(os.path.join(os.path.dirname(__file__), 'bash.sh')) as handle:
    template = handle.read()
  return (
    template
    .replace('FN', '_docopt_' + re.sub(r'[^A-Za-z0-9_]', '_', prog))
    .replace('"PROG"', shlex.quote(prog))
    .replace('"TABLES"', '\n  '.join(table_lines))
    .replace('"SOURCES"', '\n    '.join(source_lines))
  )
