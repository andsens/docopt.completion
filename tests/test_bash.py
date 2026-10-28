import re
import subprocess
import typing as T
import pytest
from docopt_completion import intermediate, tables, bash
from tests.shell import Shell

Edit = T.Callable[[T.Dict[str, T.Any]], None]


def start(text: str, edit: Edit = lambda _: None, setup: str = '') -> T.Tuple[Shell, tables.Tables]:
  result, _ = intermediate.generate(text)
  edit(result['nodes'])
  compiled = tables.compile(result)
  fn = '_docopt_' + re.sub(r'[^A-Za-z0-9_]', '_', result['prog'])
  shell = Shell(['bash', '--norc', '--noprofile', '-i'], f'''
{bash.generate(result['prog'], compiled)}
_test_wrap() {{
  COMPREPLY=()
  {fn} "$@"
  {{ [[ ${{#COMPREPLY[@]}} -eq 0 ]] || printf '%s\\n' "${{COMPREPLY[@]}}"; }} > "$DOCOPT_COMPLETION_OUT.tmp"
  mv -f "$DOCOPT_COMPLETION_OUT.tmp" "$DOCOPT_COMPLETION_OUT"
}}
complete -F _test_wrap {result['prog']}
{setup}
''')
  return shell, compiled


def expand(source: tables.Source, cur: str) -> T.List[str]:
  if isinstance(source, dict) and 'words' in source:
    words = T.cast(T.List[str], source['words'])
  elif isinstance(source, dict):
    words = subprocess.run(['bash', '-c', source['command']], capture_output=True, text=True).stdout.splitlines()
  else:
    raise NotImplementedError(source)
  return [word for word in words if word.startswith(cur)]


def expected(compiled: tables.Tables, line: str) -> T.List[str]:
  *words, cur = line.split(' ')
  completion = tables.complete(compiled, words, cur)
  candidates = [word for word, _ in completion.words if word.startswith(cur)]
  candidates += [
    completion.prefix + value for source in completion.sources
    for value in expand(source, cur[len(completion.prefix):])
  ]
  # Readline replaces only what follows the last word break
  piece = T.cast(re.Match[str], re.search(r'[^=:]*$', cur)).group(0)
  return sorted(candidate[len(cur) - len(piece):] for candidate in candidates)


def check(text: str, lines: T.List[str], edit: Edit = lambda _: None):
  shell, compiled = start(text, edit)
  prog = T.cast(str, intermediate.generate(text)[0]['prog'])
  try:
    mismatches = [
      (line, got, want) for line in lines
      if (got := sorted(shell.complete(f'{prog} {line}'))) != (want := expected(compiled, line))
    ]
  finally:
    shell.close()
  assert mismatches == []


naval_fate = '''Naval Fate.
Usage:
  naval_fate <name> move <x> <y> [--speed=<kn>]
  naval_fate shoot <x> <y>

Options:
  -s, --speed=<kn>  Speed in knots [default: 10].
'''


def test_naval_fate():
  def edit(nodes: T.Dict[str, T.Any]):
    nodes['<name>']['complete'] = {'command': "printf '%s\\n' alpha beta"}
    nodes['<x>']['complete'] = {'words': ['1', '2']}
  check(naval_fate, [
    '', 's', 'al', 'ship ', 'ship m', 'shoot ', 'ship move ', 'ship move 1', 'ship move 1 2 ',
    'ship move 1 2 -', 'ship move 1 2 --', 'ship move --speed ', 'ship move -s ', 'ship move --speed=',
    'ship move --speed=1', 'ship move --sp=', 'ship move -s5 ', 'ship move --speed 5 ',
    'ship move 1 2 3 ', 'ship move --speed=5 -',
  ], edit)


def test_option_scope():
  check('Usage:\n  prog a [-v] <x>\n  prog b [-q]', ['-', 'a -', 'b -', 'a -v -'])


def test_repeatable():
  check('Usage: prog [-v...] <x>', ['-v -', '-v -v -'])


def test_stacked_shorts():
  check('Usage: prog [-v] [-o <file>] <x>\n\nOptions:\n  -v\n  -o <file>\n', [
    '-vo ', '-vofoo ', '-vo foo -', '-o',
  ], lambda nodes: nodes['-o'].update(complete={'words': ['out']}))


def test_separator():
  check('Usage: prog [-v] [--] <x>...', ['-- ', '-- -v ', '-- -', '-v -- ', '-v -'],
        lambda nodes: nodes['<x>'].update(complete={'words': ['w1', 'w2']}))


def test_wordbreaks_in_positionals():
  def edit(nodes: T.Dict[str, T.Any]):
    nodes['<x>']['complete'] = {'words': ['a:b', 'a:c']}
    nodes['<y>']['complete'] = {'words': ['yy']}
  check('Usage: prog <x> <y>', ['a:b ', 'a:', 'a:b', 'a'], edit)


@pytest.fixture
def files():
  shell, _ = start(
    'Usage: prog [--config=<file>] <dir>',
    setup='mkdir -p fs/sub fs/subway && : > fs/a.txt && cd fs',
  )
  yield shell
  shell.close()


def test_files_and_dirs(files: Shell):
  assert sorted(files.complete('prog su')) == ['sub', 'subway']
  assert sorted(files.complete('prog ')) == ['sub', 'subway']
  assert sorted(files.complete('prog --config ')) == ['a.txt', 'sub', 'subway']
  assert files.complete('prog --config=a') == ['a.txt']


def test_end_to_end():
  # The real completion, and a stub program that records its argv
  result, _ = intermediate.generate(naval_fate)
  result['nodes']['<x>']['complete'] = {'words': ['a:b']}
  shell = Shell(['bash', '--norc', '--noprofile', '-i'], f'''
{bash.generate(result['prog'], tables.compile(result))}
naval_fate() {{
  printf '%s\\n' "$@" > "$DOCOPT_COMPLETION_OUT.tmp"
  mv -f "$DOCOPT_COMPLETION_OUT.tmp" "$DOCOPT_COMPLETION_OUT"
}}
''')
  try:
    assert shell.run('naval_fate ship move --speed=\t') == ['ship', 'move', '--speed=10']
    assert shell.run('naval_fate ship move --speed=1\t') == ['ship', 'move', '--speed=10']
    assert shell.run('naval_fate ship move --sp=\t') == ['ship', 'move', '--sp=10']
    assert shell.run('naval_fate ship m\ta:\t') == ['ship', 'move', 'a:b']
    assert shell.run('naval_fate sh\t') == ['shoot']
  finally:
    shell.close()
