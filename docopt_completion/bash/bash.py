import os
import typing as T
import docopt_parser as P
from docopt_completion.bash.code import Code

helper_map = {
  P.Choice: 'choice',
  P.Sequence: 'sequence',
  P.Optional: 'optional',
  P.Repeatable: 'repeatable',
  P.Command: 'cmd',
  P.Argument: 'arg',
  P.ArgumentSeparator: 'argsep',
  P.Option: 'opt',
}

AstGroup = P.Choice | P.Sequence | P.Optional | P.Repeatable
AstLeaf = P.Command | P.Argument | P.ArgumentSeparator | P.Option

class Completer(object):
  prog: str
  root: "Group"
  groups: T.List["Group"]
  leaves: T.List["Leaf"]
  template: Code

  def __init__(self, prog: str, root: AstGroup):
    super().__init__()
    self.prog = prog
    self.groups = []
    self.leaves = []
    with open(os.path.join(os.path.dirname(__file__), 'template.sh'), 'r') as handle:
      self.template = Code(handle.read())

    node_idx = -1

    def wrap_ast_nodes(node: AstGroup) -> Group:
      nonlocal node_idx
      new_items: T.List[Node] = []
      node_idx += 1
      group_idx = node_idx
      for item in node.items:
        if isinstance(item, AstGroup):
          new_items.append(wrap_ast_nodes(item))
        else:
          new_item = next((leaf for leaf in self.leaves if item == leaf.ast_node), None)
          if new_item is None:
            node_idx += 1
            new_item = Leaf(T.cast(AstLeaf, item), node_idx)
            self.leaves.append(new_item)
          new_items.append(new_item)
      group = Group(node, group_idx, new_items)
      self.groups.append(group)
      return group
    self.root = wrap_ast_nodes(root)

  def __str__(self):
    return str(self.template.replace({
      '"GROUPS"': '\n'.join(map(repr, self.groups)),
      '"LEAVES"': '\n'.join(map(repr, self.leaves)),
    }))

class Node(object):
  ast_node: P.Node
  idx: int

  def __init__(self, ast_node: P.Node, idx: int):
    super().__init__()
    self.ast_node = ast_node
    self.idx = idx

class Group(Node):
  ast_node: AstGroup
  items: T.Sequence[Node]

  def __init__(self, ast_node: AstGroup, idx: int, items: T.Sequence[Node]):
    super().__init__(ast_node, idx)
    self.items = items

  _T = T.TypeVar('_T')

  def reduce(self, function: T.Callable[[_T, Node], _T], memo: _T) -> _T:
    for item in iter(self.items):
      memo = function(memo, item)
      if isinstance(item, Group):
        memo = item.reduce(function, memo)
    return memo

  def __repr__(self):
    return (
      f'node_{self.idx}() {{ '
      f'{helper_map[type(self.ast_node)]} {" ".join([str(n.idx) for n in self.items])}; }}'
    )

class Leaf(Node):
  ast_node: AstLeaf

  def __init__(self, ast_node: AstLeaf, idx: int):
    super().__init__(ast_node, idx)

  def __repr__(self):
    return f'node_{self.idx}() {{ {helper_map[type(self.ast_node)]} "{self.ast_node.ident}"; }}'

  def __hash__(self) -> int:
    return self.ast_node.__hash__()

  def __eq__(self, other: T.Any) -> bool:
    return self.ast_node.__eq__(other)


def generate_completion(prog: str, root: P.Group):
  return Completer(prog, T.cast(AstGroup, root))
