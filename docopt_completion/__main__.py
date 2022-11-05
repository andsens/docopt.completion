#!/usr/bin/env python3
import logging
import os
import sys
import typing as T
import docopt
import termcolor
import docopt_parser as P
from docopt_completion import __doc__ as pkg_doc, \
  __name__ as root_name, __version__
from docopt_completion.bash import bash

log = logging.getLogger(root_name)

__doc__: str = T.cast(str, pkg_doc) + """
Usage:
  docopt-parser generate [-|COMMAND]
  docopt-parser -h
  docopt-parser --version

Options:
  --help -h  Show this help screen
  --version  Show the docopt.completion version
"""
Params = T.TypedDict('Params', {'--yaml': bool, 'generate': bool, '-': bool})

def docopt_completion(params: Params):
  try:
    text = ''
    if params['-']:
      text = sys.stdin.read()
    root = P.parse(text)
    prog = P.get_prog(text).elm
    bash_completion = bash.generate_completion(prog, root)
    sys.stdout.write(str(bash_completion))
  except P.DocoptError as error:
    log.error(str(error))
    sys.exit(error.exit_code)


def setup_logging():
  level_colors = {
    logging.ERROR: 'red',
    logging.WARN: 'yellow',
  }

  class ColorFormatter(logging.Formatter):

    def format(self, record: logging.LogRecord):
      record.msg = termcolor.colored(str(record.msg), level_colors.get(record.levelno, None))
      return super().format(record)

  stderr = logging.StreamHandler(sys.stderr)
  if os.isatty(2):
    stderr.setFormatter(ColorFormatter())
  log.setLevel(level=logging.INFO)
  log.addHandler(stderr)


def main():
  setup_logging()
  params = T.cast(Params, docopt.docopt(__doc__, version=__version__))
  docopt_completion(params)


if __name__ == '__main__':
  main()
