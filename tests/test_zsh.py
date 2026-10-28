import typing as T
import pytest
from docopt_completion import intermediate, tables, zsh
from tests.shell import Shell
from tests.test_bash import Edit, naval_fate, naval_fate_edit, cases

record = '''
_docopt_record() { print -rl -- "$@" >> "$DOCOPT_COMPLETION_OUT.tmp"; }
_describe() { local e; for e in "${(@P)4}"; do _docopt_record "describe:$e"; done; }
compadd() { shift "${@[(i)--]}"; local w; for w in "$@"; do _docopt_record "add:$IPREFIX$w"; done; }
''' + ''.join(
  f'{fn}() {{ _docopt_record "source:{fn}${{1:+ $*}}"; }}\n'
  for fn in sorted({code.split(' ')[0] for code in zsh.compsys.values()})
)


def start(text: str, edit: Edit) -> T.Tuple[Shell, tables.Tables, str]:
  result, _ = intermediate.generate(text)
  edit(result['nodes'])
  compiled = tables.compile(result)
  shell = Shell(['zsh', '-f', '-i'], f'''
autoload -U compinit && compinit -u -d "$HOME/.zcompdump"
{zsh.generate(result['prog'], compiled)}
{record}
_test_wrap() {{
  : > "$DOCOPT_COMPLETION_OUT.tmp"
  _{result['prog']}
  mv -f "$DOCOPT_COMPLETION_OUT.tmp" "$DOCOPT_COMPLETION_OUT"
}}
compdef _test_wrap {result['prog']}
''')
  return shell, compiled, result['prog']


def expected(compiled: tables.Tables, line: str) -> T.List[str]:
  *words, cur = line.split(' ')
  completion = tables.complete(compiled, words, cur)
  result = [
    'describe:' + word.replace(':', '\\:') + (f':{description}' if description else '')
    for word, description in completion.words
  ]
  for source in completion.sources:
    if isinstance(source, str):
      result.append(f'source:{zsh.compsys[source]}')
    elif 'words' in source:
      result += [f'add:{completion.prefix}{word}' for word in source['words']]
    else:
      result += ['add:alpha', 'add:beta']  # the command in naval_fate_edit
  return sorted(result)


def check(text: str, lines: T.List[str], edit: Edit = lambda _: None):
  shell, compiled, prog = start(text, edit)
  try:
    mismatches = [
      (line, got, want) for line in lines
      if (got := sorted(shell.complete(f'{prog} {line}'))) != (want := expected(compiled, line))
    ]
  finally:
    shell.close()
  assert mismatches == []


@pytest.mark.parametrize('name', cases.keys())
def test_cases(name: str):
  text, lines, edit = cases[name]
  check(text, lines, edit)


def test_quoted_words():
  # zsh keeps the quotes in $words, the runtime removes them
  shell, _, _ = start('Usage: prog a (b|c)', lambda _: None)
  try:
    for line in ["prog 'a' ", 'prog "a" ', 'prog \\a ']:
      assert sorted(shell.complete(line)) == ['describe:b', 'describe:c']
  finally:
    shell.close()


def test_end_to_end(tmp_path: T.Any):
  # The real compsys with the script autoloaded from $fpath, and a stub program that records its argv
  result, _ = intermediate.generate(naval_fate)
  naval_fate_edit(result['nodes'])
  result['nodes']['<x>']['complete'] = {'words': ['a:b']}
  result['nodes']['shoot']['description'] = 'Fire at a position'
  (tmp_path / '_naval_fate').write_text(zsh.generate(result['prog'], tables.compile(result)))
  shell = Shell(['zsh', '-f', '-i'], f'''
fpath=({tmp_path} $fpath)
autoload -U compinit && compinit -u -d "$HOME/.zcompdump"
naval_fate() {{
  print -rl -- "$@" > "$DOCOPT_COMPLETION_OUT.tmp"
  mv -f "$DOCOPT_COMPLETION_OUT.tmp" "$DOCOPT_COMPLETION_OUT"
}}
''')
  try:
    assert shell.run('naval_fate ship move --speed=\t') == ['ship', 'move', '--speed=10']
    assert shell.run('naval_fate ship move --sp=\t') == ['ship', 'move', '--sp=10']
    assert shell.run('naval_fate ship m\ta:\t') == ['ship', 'move', 'a:b']
    assert shell.run('naval_fate sh\t') == ['shoot']
    assert shell.run('naval_fate al\t') == ['alpha']
    screen = shell.screen('naval_fate ship move 1 2 -\t')
    assert 'Speed in knots' in screen
    assert 'Fire at a position' in shell.screen('naval_fate \t')
  finally:
    shell.close()
