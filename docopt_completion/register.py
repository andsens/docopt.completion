"""
Completion for a docopt program that has none, generated from its `--help`. The script regenerates
itself when the program's resolved path or modification time changes.
"""
import os
import shutil
import subprocess
import typing as T
import docopt_parser as P
from docopt_completion import intermediate, tables, bash, zsh


class NotDocoptError(P.DocoptError):
  pass


def default_dir(shell: str, env: T.Mapping[str, str]) -> str:
  """Where bash-completion lazy-loads user completions from; zsh has no such place"""
  data = env.get('XDG_DATA_HOME') or os.path.join(env['HOME'], '.local', 'share')
  if shell == 'bash':
    user_dir = env.get('BASH_COMPLETION_USER_DIR', '').split(':')[0] or os.path.join(data, 'bash-completion')
    return os.path.join(user_dir, 'completions')
  return os.path.join(data, 'zsh', 'site-functions')


def register(shell: str, command: str, directory: str) -> str:
  """Writes the completion script for `command` to `directory` and returns its path"""
  found = shutil.which(command)
  if found is None:
    raise P.DocoptError(f'{command} not found')
  binary = os.path.realpath(found)
  try:
    text = subprocess.run([found, '--help'], capture_output=True, text=True, timeout=10, check=True).stdout
  except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
    raise P.DocoptError(f'`{command} --help` failed: {error}') from error
  result, _ = intermediate.generate(text)
  for key, node in T.cast(T.Dict[str, T.Dict[str, T.Any]], result['nodes']).items():
    if node['type'] == 'argument' and intermediate.placeholder_word(key) in ('option', 'options'):
      raise NotDocoptError(f'The help of {command} looks GNU style ({key}), not docopt')
  compiled = tables.compile(result)
  # A path names a file, the usage names the command that runs it
  name = result['prog'] if os.sep in command else command
  path = os.path.join(directory, f'{name}.bash' if shell == 'bash' else f'_{name}')
  refresh = (binary, path, ['docopt.completion', 'register', f'--dir={directory}', shell, command])
  code = (bash if shell == 'bash' else zsh).generate(name, compiled, refresh)
  os.makedirs(directory, exist_ok=True)
  with open(path, 'w') as handle:
    handle.write(code)
  # The script carries the binary's mtime, a mismatch means the binary changed
  stat = os.stat(binary)
  os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns))
  return path
