import typing as T
import pytest
from docopt_parser import DocoptError
from docopt_completion import intermediate, tables

naval_fate = '''Naval Fate.
Usage:
  naval_fate <name> move <x> <y> [--speed=<kn>]
  naval_fate shoot <x> <y>

Options:
  -s, --speed=<kn>  Speed in knots [default: 10].
'''


def completer(text: str, edit: T.Callable[[T.Dict[str, T.Any]], None] = lambda _: None):
  result, _ = intermediate.generate(text)
  edit(result['nodes'])
  compiled = tables.compile(result)

  def complete(line: str) -> T.Tuple[T.List[str], T.List[tables.Source], str]:
    *words, cur = line.split(' ')
    completion = tables.complete(compiled, words, cur)
    return [word for word, _ in completion.words], completion.sources, completion.prefix
  return complete


def test_naval_fate_positionals():
  complete = completer(naval_fate, lambda nodes: nodes['<x>'].update(complete={'words': ['1', '2']}))
  assert complete('') == (['shoot'], [], '')
  assert complete('ship ') == (['move'], [], '')
  assert complete('ship move ') == ([], [{'words': ['1', '2']}], '')
  assert complete('ship move 1 2 ') == (['--speed', '-s'], [], '')
  assert complete('ship move 1 2 3 ') == ([], [], '')


def test_command_names_are_also_arguments():
  # `naval_fate shoot move 1 2` is valid, <name> is "shoot"
  complete = completer(naval_fate)
  assert complete('shoot ')[0] == ['move']


def test_option_values():
  complete = completer(naval_fate)
  assert complete('ship move --speed ') == ([], [{'words': ['10']}], '')
  assert complete('ship move -s ') == ([], [{'words': ['10']}], '')
  assert complete('ship move --speed=') == ([], [{'words': ['10']}], '--speed=')
  assert complete('ship move --sp=') == ([], [{'words': ['10']}], '--sp=')
  # The value is skipped, positionals continue after it
  assert complete('ship move --speed 5 ') == ([], [], '')
  assert complete('ship move -s5 ') == ([], [], '')


def test_options_anywhere_and_used_once():
  complete = completer(naval_fate)
  assert complete('ship move -') == (['--speed', '-s'], [], '')
  assert complete('ship move --speed=5 -') == ([], [], '')
  assert complete('ship move -s 5 1 2 ') == ([], [], '')


def test_option_scope_follows_the_branch():
  complete = completer('''Usage:
  prog a [-v] <x>
  prog b [-q]
''')
  assert complete('-')[0] == ['-v', '-q']
  assert complete('a -')[0] == ['-v']
  assert complete('b -')[0] == ['-q']


def test_repeatable_options():
  complete = completer('Usage: prog [-v...] <x>')
  assert complete('-v -')[0] == ['-v']
  complete = completer('Usage: prog [-v] <x>')
  assert complete('-v -')[0] == []


def test_stacked_shorts():
  complete = completer('''Usage: prog [-v] [-o <file>] <x>

Options:
  -v
  -o <file>
''', lambda nodes: nodes['<x>'].update(complete='hosts'))
  assert complete('-vo ') == ([], ['files'], '')
  assert complete('-vofoo ') == ([], ['hosts'], '')
  assert complete('-vo foo -')[0] == []


def test_separator():
  complete = completer('Usage: prog [-v] [--] <file>...')
  assert complete('-- ') == ([], ['files'], '')
  # After -- options are positional, -v is a file
  assert complete('-- -v ') == ([], ['files'], '')
  assert complete('-- -') == ([], ['files'], '')


def test_options_when_nothing_positional_is_left():
  complete = completer('Usage: prog <x> [--force]')
  assert complete('foo ')[0] == ['--force']


def test_command_descriptions():
  result, _ = intermediate.generate(naval_fate)
  result['nodes']['shoot']['description'] = 'Fire!'
  compiled = tables.compile(result)
  assert tables.complete(compiled, [], '').words == [('shoot', 'Fire!')]


def test_split_nodes_complete_separately():
  def split(nodes: T.Dict[str, T.Any]):
    nodes['<x>']['complete'] = 'files'
    nodes['shoot <x>'] = {'type': 'argument', 'complete': 'hosts'}
  result, _ = intermediate.generate(naval_fate)
  split(result['nodes'])
  result, _ = intermediate.generate(naval_fate, result)
  compiled = tables.compile(result)
  assert tables.complete(compiled, ['ship', 'move'], '').sources == ['files']
  # "shoot" is also a valid <name>, so both apply after it
  assert tables.complete(compiled, ['shoot'], '').sources == ['hosts']
  assert tables.complete(compiled, ['shoot', 'move'], '').sources == ['files']


def test_unknown_source():
  result, _ = intermediate.generate(naval_fate)
  result['nodes']['<x>']['complete'] = 'everything'
  with pytest.raises(DocoptError):
    tables.compile(result)


def test_options_before_a_positional_stay_in_scope():
  # docopt matches options anywhere: `prog a -v x` is valid
  complete = completer('Usage: prog [-v] a <x> | prog b')
  assert complete('a -')[0] == ['-v']
  assert complete('b -')[0] == []
