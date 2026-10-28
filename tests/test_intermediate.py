import typing as T
import pytest
from docopt_completion import intermediate

naval_fate = '''Naval Fate.
Usage:
  naval_fate <name> move <x> <y> [--speed=<kn>]
  naval_fate shoot <x> <y>

Options:
  -s, --speed=<kn>  Speed in knots [default: 10].
'''


def test_naval_fate():
  result, orphans = intermediate.generate(naval_fate)
  assert orphans == []
  assert result == {
    'prog': 'naval_fate',
    'usage': {'choice': [
      {'sequence': ['<name>', 'move', '<x>', '<y>', {'optional': ['--speed']}]},
      {'sequence': ['shoot', '<x>', '<y>']},
    ]},
    'nodes': {
      '<name>': {'type': 'argument', 'complete': 'none'},
      'move': {'type': 'command'},
      '<x>': {'type': 'argument', 'complete': 'none'},
      '<y>': {'type': 'argument', 'complete': 'none'},
      '--speed': {
        'type': 'option', 'short': '-s', 'argument': '<kn>', 'default': ['10'],
        'description': 'Speed in knots.', 'complete': {'words': ['10']},
      },
      'shoot': {'type': 'command'},
    },
  }


@pytest.mark.parametrize('placeholder, complete', [
  ('<file>', 'files'),
  ('FILE', 'files'),
  ('<config-file>', 'files'),
  ('<OUTPUT_FILE>', 'files'),
  ('<files>', 'files'),
  ('<path>', 'files'),
  ('<outputDir>', 'dirs'),
  ('<directories>', 'dirs'),
  ('<hostname>', 'hosts'),
  ('<user>', 'users'),
  ('<group>', 'groups'),
  ('<cmd>', 'commands'),
  ('<sig>', 'signals'),
  ('<pid>', 'processes'),
  ('<x>', 'none'),
  ('<profile>', 'none'),
])
def test_placeholder_defaults(placeholder: str, complete: str):
  result, _ = intermediate.generate(f'Usage: prog {placeholder}')
  assert result['nodes'][placeholder]['complete'] == complete


def test_option_default_and_placeholder():
  result, _ = intermediate.generate('''Usage: prog [options]

Options:
  --config=<file>  Config [default: ~/.prog]
''')
  assert result['nodes']['--config']['complete'] == [{'words': ['~/.prog']}, 'files']


def test_annotations_survive_regeneration():
  previous, _ = intermediate.generate(naval_fate)
  previous['nodes']['<name>']['complete'] = {'command': 'naval_fate list'}
  previous['nodes']['move']['description'] = 'Move a ship'
  del previous['nodes']['--speed']['complete']
  previous['nodes']['--speed']['default'] = ['stale']
  changed = naval_fate.replace('[default: 10]', '[default: 20]')
  result, orphans = intermediate.generate(changed, previous)
  assert orphans == []
  assert result['nodes']['<name>']['complete'] == {'command': 'naval_fate list'}
  assert result['nodes']['move']['description'] == 'Move a ship'
  # Parsed fields are refreshed, removed annotations reset to their default
  assert result['nodes']['--speed']['default'] == ['20']
  assert result['nodes']['--speed']['complete'] == {'words': ['20']}


def test_orphans():
  previous, _ = intermediate.generate(naval_fate)
  previous['nodes']['<gone>'] = {'type': 'argument', 'complete': 'files'}
  _, orphans = intermediate.generate(naval_fate, previous)
  assert orphans == ['<gone>']


def split(key: str, complete: T.Any):
  previous, _ = intermediate.generate(naval_fate)
  previous['nodes'][key] = {'type': 'argument', 'complete': complete}
  result, orphans = intermediate.generate(naval_fate, previous)
  assert orphans == []
  return result


def test_split_by_command():
  result = split('shoot <x>', 'hosts')
  assert result['usage']['choice'][0]['sequence'][2] == '<x>'
  assert result['usage']['choice'][1]['sequence'][1] == 'shoot <x>'
  assert result['nodes']['shoot <x>']['complete'] == 'hosts'
  assert result['nodes']['<x>']['complete'] == 'none'


def test_split_by_occurrence():
  result = split('<x>#2', 'hosts')
  assert result['usage']['choice'][1]['sequence'][1] == '<x>#2'


def test_longest_qualifier_wins():
  previous, _ = intermediate.generate('Usage: prog a b <x>')
  previous['nodes']['a <x>'] = {'type': 'argument', 'complete': 'files'}
  previous['nodes']['a b <x>'] = {'type': 'argument', 'complete': 'dirs'}
  result, orphans = intermediate.generate('Usage: prog a b <x>', previous)
  assert result['usage'] == {'sequence': ['a', 'b', 'a b <x>']}
  assert orphans == ['<x>', 'a <x>']


def test_cli_updates_file_in_place(tmp_path: T.Any, monkeypatch: pytest.MonkeyPatch):
  import io
  import yaml
  from docopt_completion.__main__ import docopt_completion
  path = tmp_path / 'naval_fate.yaml'
  previous, _ = intermediate.generate(naval_fate)
  previous['nodes']['move']['description'] = 'Move a ship'
  path.write_text(yaml.safe_dump(previous))
  monkeypatch.setattr('sys.stdin', io.StringIO(naval_fate))
  docopt_completion({'intermediate': True, 'FILE': str(path)})
  assert yaml.safe_load(path.read_text())['nodes']['move']['description'] == 'Move a ship'
