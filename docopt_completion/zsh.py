import typing as T
import docopt_parser as P
from ordered_set import OrderedSet


class Main(object):
  prog: str
  root: P.Group

  def __init__(self, prog: str, root: P.Group):
    super().__init__()
    self.prog = prog
    self.root = root

  def __repr__(self):
    def first_cmd(group: P.Group) -> P.Command | None:
      for item in group.items:
        if isinstance(item, P.Group):
          sub_item = first_cmd(item)
          if sub_item is not None:
            return sub_item
        if isinstance(item, P.Command):
          return item
      return None

    cmds: OrderedSet[str] = OrderedSet([])
    for item in self.root.items:
      if isinstance(item, P.Command):
        cmds.add(item.ident)
      if not isinstance(item, P.Group):
        continue
      cmd = first_cmd(item)
      if cmd is not None:
        cmds.add(cmd.ident)

    return f'''#compdef {self.prog}

_main() {{
  local context state line curcontext="$curcontext" ret=1
  _arguments -n : \\
    '1:commands:({' '.join(cmds)})' \\
    '*::arguments:->arguments' \\
    && ret=0
}}

_main "$@"
'''

def generate_completion(prog: str, root: P.Group):
  return Main(prog, root)
