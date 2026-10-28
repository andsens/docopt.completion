"""
Match tables compiled from the intermediate, the input for the shell generators.

The positional leaves (commands, arguments, `--`) form an automaton that is compiled to a DFA
over the command names, `--` and any other word. Options take no part in the ordering, docopt
matches them anywhere. Instead every state lists the options that lie on some path through it.

`complete()` is the reference for what the shell runtimes do with the tables.
"""
import typing as T
from dataclasses import dataclass, field
from docopt_parser import DocoptError

Source = T.Union[str, T.Dict[str, T.Any]]
builtin_sources = ('files', 'dirs', 'hosts', 'users', 'groups', 'commands', 'signals', 'processes')

@dataclass
class Option:
  names: T.List[str]
  argument: bool
  repeatable: bool
  description: "str | None"
  complete: T.List[Source]

@dataclass
class State:
  # command name -> (next state, description)
  commands: T.Dict[str, T.Tuple[int, "str | None"]] = field(default_factory=dict[str, T.Tuple[int, "str | None"]])
  # next state for `--` and for any other word
  separator: "int | None" = None
  other: "int | None" = None
  # completion sources of the arguments that `other` consumes
  complete: T.List[Source] = field(default_factory=list[Source])
  # indexes into Tables.options
  options: T.List[int] = field(default_factory=list[int])

@dataclass
class Tables:
  options: T.List[Option]
  states: T.List[State]


def ident(key: str) -> str:
  """`shoot <x>#2` -> `<x>`"""
  return key.split(' ')[-1].split('#')[0]


def sources(key: str, complete: T.Any) -> T.List[Source]:
  items = T.cast(T.List[T.Any], complete if isinstance(complete, list) else [complete])
  result: T.List[Source] = []
  for item in items:
    if item == 'none':
      continue
    if item in builtin_sources:
      result.append(T.cast(str, item))
      continue
    if isinstance(item, dict):
      source = T.cast(T.Dict[str, T.Any], item)
      if len(source) == 1 and (isinstance(source.get('words'), list) or isinstance(source.get('command'), str)):
        result.append(source)
        continue
    raise DocoptError(f'{key}: unknown completion source {item!r}')
  return result


Label = T.Tuple[str, str]  # (node type, key)
# An NFA state and the options passed on the way to it
Item = T.Tuple[int, T.FrozenSet[str]]

def compile(intermediate: T.Dict[str, T.Any]) -> Tables:
  nodes: T.Dict[str, T.Dict[str, T.Any]] = intermediate['nodes']
  edges: T.List[T.List[T.Tuple["Label | None", int]]] = []
  repeatable_options: T.Set[str] = set()

  def new_state() -> int:
    edges.append([])
    return len(edges) - 1

  def build(usage: T.Any, start: int, repeated: bool = False) -> int:
    if isinstance(usage, str):
      end = new_state()
      edges[start].append(((nodes[usage]['type'], usage), end))
      if repeated and nodes[usage]['type'] == 'option':
        repeatable_options.add(usage)
      return end
    [(kind, items)] = T.cast(T.Dict[str, T.List[T.Any]], usage).items()
    if kind == 'choice':
      end = new_state()
      for item in items:
        edges[build(item, start, repeated)].append((None, end))
      return end
    if kind == 'optional':
      # docopt makes every item of [a b] optional on its own
      for item in items:
        end = new_state()
        edges[start].append((None, end))
        edges[build(item, start, repeated)].append((None, end))
        start = end
      return start
    if kind == 'repeatable':
      loop = new_state()
      edges[start].append((None, loop))
      end = build({'sequence': items}, loop, True)
      edges[end].append((None, loop))
      return end
    for item in items:
      start = build(item, start, repeated)
    return start

  start = new_state()
  accept = build(intermediate['usage'], start)

  # States reachable from each state
  reach: T.List[T.Set[int]] = []
  for state in range(len(edges)):
    seen = {state}
    todo = [state]
    while todo:
      for _, target in edges[todo.pop()]:
        if target not in seen:
          seen.add(target)
          todo.append(target)
    reach.append(seen)
  option_edges = [
    (source, label[1], target) for source in range(len(edges))
    for label, target in edges[source] if label is not None and label[0] == 'option'
  ]

  def after(state: int) -> T.Set[str]:
    """Options on some path from `state` to the end"""
    return {key for source, key, target in option_edges if source in reach[state] and accept in reach[target]}

  def closure(items: T.Iterable["Item"]) -> T.FrozenSet["Item"]:
    passed_by: T.Dict[int, T.FrozenSet[str]] = {}
    todo = list(items)
    while todo:
      state, passed = todo.pop()
      if state in passed_by and passed <= passed_by[state]:
        continue
      passed_by[state] = passed = passed_by.get(state, frozenset()) | passed
      for label, target in edges[state]:
        if label is None:
          todo.append((target, passed))
        elif label[0] == 'option':
          todo.append((target, passed | {label[1]}))
    return frozenset(passed_by.items())

  option_keys = [key for key, node in nodes.items() if node['type'] == 'option']
  options = [
    Option(
      names=[ident(key)] + ([nodes[key]['short']] if 'short' in nodes[key] else []),
      argument='argument' in nodes[key],
      repeatable=key in repeatable_options,
      description=nodes[key].get('description'),
      complete=sources(key, nodes[key].get('complete', 'none')),
    ) for key in option_keys
  ]

  dfa: T.Dict[T.FrozenSet[Item], int] = {}
  states: T.List[State] = []

  def dfa_state(items: T.FrozenSet[Item]) -> "int | None":
    if not items:
      return None
    if items in dfa:
      return dfa[items]
    index = dfa[items] = len(states)
    state = State()
    states.append(state)
    outgoing = [
      (label, (target, passed)) for s, passed in items
      for label, target in edges[s] if label is not None and label[0] != 'option'
    ]
    arguments = {target for (kind, _), target in outgoing if kind == 'argument'}
    for (kind, key), _ in outgoing:
      if kind == 'command':
        name = ident(key)
        targets = {t for (k, other_key), t in outgoing if k == 'command' and ident(other_key) == name}
        next_state = T.cast(int, dfa_state(closure(targets | arguments)))
        description = state.commands.get(name, (0, None))[1] or nodes[key].get('description')
        state.commands[name] = (next_state, description)
      elif kind == 'argument':
        for source in sources(key, nodes[key].get('complete', 'none')):
          if source not in state.complete:
            state.complete.append(source)
    separators = {target for (kind, _), target in outgoing if kind == 'separator'}
    state.separator = dfa_state(closure(separators | arguments))
    state.other = dfa_state(closure(arguments))
    in_scope = set[str]().union(*(passed | after(s) for s, passed in items))
    state.options = [i for i, key in enumerate(option_keys) if key in in_scope]
    return index

  dfa_state(closure([(start, frozenset())]))
  return Tables(options, states)


@dataclass
class Completion:
  # Literal candidates with their descriptions
  words: T.List[T.Tuple[str, "str | None"]] = field(default_factory=list[T.Tuple[str, "str | None"]])
  # Sources for the shell to expand
  sources: T.List[Source] = field(default_factory=list[Source])
  # Prepended to every candidate, e.g. `--speed=`
  prefix: str = ''


def complete(tables: Tables, words: T.List[str], cur: str) -> Completion:
  """Candidates for `cur` after `words` (without the program name). Not filtered by `cur`."""
  state: "int | None" = 0
  used: T.Set[int] = set()
  expect: "Option | None" = None
  positional_only = False

  def find(name: str, prefix: bool) -> "int | None":
    in_scope = tables.states[state].options if state is not None else []
    matches = [i for i, o in enumerate(tables.options) if name in o.names]
    if not matches and prefix:
      matches = [i for i, o in enumerate(tables.options) if any(n.startswith(name) for n in o.names[:1])]
      if len({tables.options[i].names[0] for i in matches}) > 1:
        return None
    return next((i for i in matches if i in in_scope), next(iter(matches), None))

  for word in words:
    if state is None:
      return Completion()
    if expect is not None:
      expect = None
    elif not positional_only and word == '--':
      positional_only = True
      state = tables.states[state].separator
    elif not positional_only and word.startswith('--'):
      name, eq, _ = word.partition('=')
      if (i := find(name, True)) is not None:
        used.add(i)
        if tables.options[i].argument and not eq:
          expect = tables.options[i]
    elif not positional_only and word.startswith('-') and word != '-':
      for pos in range(1, len(word)):
        if (i := find('-' + word[pos], False)) is not None:
          used.add(i)
          if tables.options[i].argument:
            if pos == len(word) - 1:
              expect = tables.options[i]
            break
    else:
      current = tables.states[state]
      state = current.commands[word][0] if word in current.commands else current.other

  if state is None:
    return Completion()
  if expect is not None:
    return Completion(sources=expect.complete)
  if not positional_only and cur.startswith('--') and '=' in cur:
    name = cur.partition('=')[0]
    if (i := find(name, True)) is not None and tables.options[i].argument:
      return Completion(sources=tables.options[i].complete, prefix=name + '=')
    return Completion()
  current = tables.states[state]
  options = Completion(words=[
    (name, tables.options[i].description)
    for i in current.options if i not in used or tables.options[i].repeatable
    for name in tables.options[i].names
  ])
  if positional_only:
    options = Completion()
  if cur.startswith('-') and not positional_only:
    return options
  if not current.commands and current.other is None:
    return options
  return Completion(
    words=[(name, description) for name, (_, description) in current.commands.items()],
    sources=current.complete,
  )
