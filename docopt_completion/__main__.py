#!/usr/bin/env python3
import logging
import os
import sys
import typing as T
import docopt
import termcolor
import yaml
import docopt_parser as P
from docopt_completion import __doc__ as pkg_doc, \
  __name__ as root_name, __version__
from docopt_completion import intermediate, tables, bash, zsh, register

log = logging.getLogger(root_name)

__doc__: str = T.cast(str, pkg_doc) + """
Usage:
  docopt.completion intermediate [FILE]
  docopt.completion bash [FILE]
  docopt.completion zsh [FILE]
  docopt.completion register [--dir=DIR] (bash|zsh) COMMAND
  docopt.completion -h
  docopt.completion --version

Reads a docopt help text on stdin, except for register. FILE is an intermediate
with annotations.

Commands:
  intermediate  Write the YAML intermediate to stdout, or update FILE in place
                keeping its annotations
  bash          Write a bash completion script to stdout
  zsh           Write a zsh completion script to stdout, for a file named _<prog>
                in $fpath or to be sourced after compinit
  register      Write the completion for COMMAND from its --help, which
                regenerates itself when COMMAND changes. Without --dir the
                script goes to the shell's directory in
                ${XDG_CONFIG_HOME:-~/.config}/docopt.completion/config.yaml,
                else where bash-completion loads it from, or to
                ${XDG_DATA_HOME:-~/.local/share}/zsh/site-functions for zsh

Options:
  --help -h  Show this help screen
  --version  Show the docopt.completion version
"""
Params = T.TypedDict('Params', {
  'intermediate': bool, 'bash': bool, 'zsh': bool, 'register': bool,
  'FILE': 'str | None', '--dir': 'str | None', 'COMMAND': 'str | None',
})

def docopt_completion(params: Params):
  try:
    if params['register']:
      shell = 'bash' if params['bash'] else 'zsh'
      directory = params['--dir'] or register.default_dir(shell, os.environ)
      path = register.register(shell, T.cast(str, params['COMMAND']), directory)
      log.info(f'Wrote {path}')
      if shell == 'zsh' and params['--dir'] is None and register.configured_dir(shell, os.environ) is None:
        log.info(f'Add {directory} to $fpath before compinit if it isn\'t there already')
      return
    text = sys.stdin.read()
    previous = None
    if params['FILE'] is not None and os.path.exists(params['FILE']):
      with open(params['FILE']) as handle:
        previous = yaml.safe_load(handle)
    result, orphans = intermediate.generate(text, previous)
    for key in orphans:
      log.warning(f'{key} no longer matches anything in the usage, dropping it')
    if params['bash']:
      sys.stdout.write(bash.generate(result['prog'], tables.compile(result)))
    elif params['zsh']:
      sys.stdout.write(zsh.generate(result['prog'], tables.compile(result)))
    else:
      output = yaml.safe_dump(result, sort_keys=False, default_flow_style=None, allow_unicode=True)
      if params['FILE'] is None:
        sys.stdout.write(output)
      else:
        with open(params['FILE'], 'w') as handle:
          handle.write(output)
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
