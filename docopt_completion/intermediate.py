"""
The intermediate: a YAML document describing what to complete, generated from a docopt help text.

`usage` mirrors the usage section as nested groups whose leaves are keys into `nodes`.
`nodes` holds what was parsed (type, short, argument, default) and the annotations
(`description`, `complete`), which the user may edit and which survive regeneration.

A node key is the leaf's identifier (`<x>`, `--speed`, `move`). Adding a key that is qualified
by the commands preceding the leaf (`shoot <x>`) or by its occurrence (`<x>#2`) splits that
occurrence off into its own node on the next regeneration.
"""
import re
import typing as T
import docopt_parser as P

Usage = T.Union[str, T.Dict[str, T.List["Usage"]]]
Node = T.Dict[str, T.Any]
Intermediate = T.Dict[str, T.Any]

annotations = ('description', 'complete')

group_names: T.Dict[type, str] = {
  P.Choice: 'choice', P.Sequence: 'sequence', P.Optional: 'optional', P.Repeatable: 'repeatable',
}
leaf_types: T.Dict[type, str] = {
  P.Command: 'command', P.Argument: 'argument', P.ArgumentSeparator: 'separator', P.Option: 'option',
}

# Last word of a placeholder name -> builtin completion source
placeholder_sources = {
  'file': 'files', 'path': 'files',
  'dir': 'dirs', 'directory': 'dirs',
  'host': 'hosts', 'hostname': 'hosts',
  'user': 'users',
  'group': 'groups',
  'cmd': 'commands', 'command': 'commands',
  'signal': 'signals', 'sig': 'signals',
  'pid': 'processes',
}


def generate(text: str, previous: "Intermediate | None" = None) -> T.Tuple[Intermediate, T.List[str]]:
  """
  Returns the intermediate for `text` and the keys of `previous` that no longer match a node.
  Annotations in `previous` are kept, missing ones are filled with defaults.
  """
  root = P.parse(text)
  prog = P.get_prog(text).elm
  old_nodes: T.Dict[str, Node] = previous['nodes'] if previous else {}
  nodes: T.Dict[str, Node] = {}
  occurrences: T.Dict[str, int] = {}

  def resolve_key(ident: str, commands: T.List[str]) -> str:
    occurrences[ident] = occurrences.get(ident, 0) + 1
    if (key := f'{ident}#{occurrences[ident]}') in old_nodes:
      return key
    best, best_len = ident, 0
    for key in old_nodes:
      *qualifiers, last = key.split(' ')
      if last == ident and len(qualifiers) > best_len and is_subsequence(qualifiers, commands):
        best, best_len = key, len(qualifiers)
    return best

  def walk(node: P.Node, commands: T.List[str]) -> Usage:
    if isinstance(node, P.Group):
      items: T.List[Usage] = []
      preceding = list(commands)
      for item in node.items:
        items.append(walk(item, commands if isinstance(node, P.Choice) else preceding))
        if isinstance(item, P.Command):
          preceding.append(item.ident)
      return {group_names[type(node)]: items}
    leaf = T.cast(P.Leaf, node)
    ident = leaf.definition.ident if isinstance(leaf, P.Option) else leaf.ident
    key = resolve_key(ident, commands)
    if key not in nodes:
      nodes[key] = node_entry(leaf, old_nodes.get(key))
    return key

  usage = walk(root, [])
  return {'prog': prog, 'usage': usage, 'nodes': nodes}, [key for key in old_nodes if key not in nodes]


def node_entry(leaf: P.Leaf, old: "Node | None") -> Node:
  entry: Node = {'type': leaf_types[type(leaf)]}
  defaults: Node = {}
  if isinstance(leaf, P.Option):
    definition = leaf.definition
    if definition.short_alias and definition.short_alias != definition.ident:
      entry['short'] = definition.short_alias
    if leaf.doc:
      description = re.sub(r'\s+', ' ', re.sub(r'\[default: [^]]*\]', '', leaf.doc))
      defaults['description'] = re.sub(r' ([.,;:])', r'\1', description).strip()
    if leaf.argname:
      entry['argument'] = leaf.argname.elm
      default = leaf.default
      words = default if isinstance(default, list) else [default] if isinstance(default, str) else []
      if words:
        entry['default'] = list(words)
      defaults['complete'] = complete_default(leaf.argname.elm, words)
  elif isinstance(leaf, P.Argument):
    defaults['complete'] = complete_default(leaf.ident, [])
  for key in annotations:
    if old is not None and key in old:
      entry[key] = old[key]
    elif key in defaults:
      entry[key] = defaults[key]
  return entry


def complete_default(placeholder: str, default: T.List[str]) -> T.Any:
  sources: T.List[T.Any] = []
  if default:
    sources.append({'words': default})
  if (source := placeholder_sources.get(placeholder_word(placeholder))) is not None:
    sources.append(source)
  if not sources:
    return 'none'
  return sources[0] if len(sources) == 1 else sources


def placeholder_word(placeholder: str) -> str:
  """The last word of a placeholder, lowercased and singular: <config-files> -> file"""
  words = [w for w in re.split(r'[^A-Za-z0-9]+|(?<=[a-z])(?=[A-Z])', placeholder) if w]
  word = words[-1].lower() if words else ''
  if word not in placeholder_sources:
    if word.endswith('ies') and word[:-3] + 'y' in placeholder_sources:
      return word[:-3] + 'y'
    if word.endswith('s') and word[:-1] in placeholder_sources:
      return word[:-1]
  return word


def is_subsequence(needle: T.List[str], haystack: T.List[str]) -> bool:
  it = iter(haystack)
  return all(item in it for item in needle)
