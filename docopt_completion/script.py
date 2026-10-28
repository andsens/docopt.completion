import os
import re
import shlex
import typing as T
from docopt_completion import tables as Tb


def render(template: str, prog: str, function: str, compiled: Tb.Tables,
           source_code: T.Callable[[Tb.Source], str], base: int, descriptions: bool) -> str:
  """
  Fill a shell template with the tables as arrays. Indexes start at `base`, `base - 1` is none.
  `function` is the completion function, its helpers are prefixed with `_docopt_<prog>`.
  """
  source_sets: T.List[T.List[Tb.Source]] = []

  def source_set(sources: T.List[Tb.Source]) -> int:
    if not sources:
      return base - 1
    if sources not in source_sets:
      source_sets.append(sources)
    return source_sets.index(sources) + base

  def index(value: "int | None") -> int:
    return base - 1 if value is None else value + base

  def array(name: str, values: T.Iterable[T.Any]) -> str:
    return f'local -a {name}=(' + ' '.join(shlex.quote(str(value)) for value in values) + ')'

  options = compiled.options
  states = compiled.states
  transitions = [(i, name, target, description) for i, state in enumerate(states)
                 for name, (target, description) in state.commands.items()]
  table_lines = [
    array('opt_names', (' '.join(o.names) for o in options)),
    array('opt_arg', (int(o.argument) for o in options)),
    array('opt_rep', (int(o.repeatable) for o in options)),
    array('opt_src', (source_set(o.complete) for o in options)),
    array('cmd_state', (index(t[0]) for t in transitions)),
    array('cmd_name', (t[1] for t in transitions)),
    array('cmd_next', (index(t[2]) for t in transitions)),
    array('st_sep', (index(s.separator) for s in states)),
    array('st_other', (index(s.other) for s in states)),
    array('st_src', (source_set(s.complete) for s in states)),
    array('st_opts', (' '.join(str(index(o)) for o in s.options) for s in states)),
  ]
  if descriptions:
    table_lines += [
      array('opt_desc', (o.description or '' for o in options)),
      array('cmd_desc', (t[3] or '' for t in transitions)),
    ]
  source_lines: T.List[str] = []
  for i, sources in enumerate(source_sets):
    source_lines.append(f'{i + base})')
    source_lines += [f'  {source_code(source)}' for source in sources]
    source_lines.append('  ;;')

  with open(os.path.join(os.path.dirname(__file__), template)) as handle:
    code = handle.read()
  return (
    code
    .replace('HELPERS', '_docopt_' + re.sub(r'[^A-Za-z0-9_]', '_', prog))
    .replace('FN', function)
    .replace('"PROG"', shlex.quote(prog))
    .replace('"TABLES"', '\n  '.join(table_lines))
    .replace('"SOURCES"', '\n    '.join(source_lines))
  )
