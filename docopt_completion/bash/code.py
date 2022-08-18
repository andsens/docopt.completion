import typing as T
from itertools import chain


class Code(object):
  code: "T.Iterable[str | Code]"

  def __init__(self, code: "str | Code | T.Iterable[str | Code]"):
    super().__init__()
    if isinstance(code, str):
      self.code = [code]
    elif isinstance(code, Code):
      self.code = code.code
    else:
      self.code = code

  def replace(self, replacements: T.Dict[str, str]) -> "Code":
    return Code(replace_literal(self.code, replacements))

  def indent(self, indentation: str) -> "Code":
    return Code(indent_lines(self.code, indentation))

  def __add__(self, other: "Code"):
    return Code(chain(self.code, other.code))

  def __str__(self):
    return '\n'.join(map(str, self.code))


def replace_literal(code: T.Iterable[str | Code], replacements: T.Dict[str, str]):
  for part in code:
    if isinstance(part, Code):
      yield part.replace(replacements)
    else:
      for placeholder, replacement in replacements.items():
        part = part.replace(placeholder, str(replacement))
      yield part

def indent_lines(code: T.Iterable[str | Code], indentation: str) -> T.Generator[str | Code, None, None]:
  for part in code:
    if isinstance(part, Code):
      yield part.indent(indentation)
    else:
      yield '\n'.join(f'{indentation}{line}' for line in part.split('\n'))
