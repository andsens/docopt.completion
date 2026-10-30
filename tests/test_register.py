import os
import shutil
import sys
from pathlib import Path
import pytest
import docopt_parser
from docopt_completion import register
from tests.shell import Shell


def test_default_dir():
  assert register.default_dir('bash', {'HOME': '/h'}) == '/h/.local/share/bash-completion/completions'
  assert register.default_dir('bash', {'HOME': '/h', 'XDG_DATA_HOME': '/x'}) == '/x/bash-completion/completions'
  assert register.default_dir('bash', {'HOME': '/h', 'BASH_COMPLETION_USER_DIR': '/u:/v'}) == '/u/completions'
  assert register.default_dir('zsh', {'HOME': '/h'}) == '/h/.local/share/zsh/site-functions'
  assert register.default_dir('zsh', {'HOME': '/h', 'XDG_DATA_HOME': '/x'}) == '/x/zsh/site-functions'


def test_default_dir_from_config(tmp_path: Path):
  (tmp_path / 'docopt.completion').mkdir()
  (tmp_path / 'docopt.completion' / 'config.yaml').write_text(
    'zsh:\n  directory: $HOME/dotfiles/completions\nbash:\n  directory: ~/bash\n'
  )
  env = {'HOME': '/h', 'XDG_CONFIG_HOME': str(tmp_path)}
  assert register.default_dir('zsh', env) == '/h/dotfiles/completions'
  assert register.default_dir('bash', env) == '/h/bash'
  (tmp_path / 'docopt.completion' / 'config.yaml').write_text('zsh:\n  directory: ${HOME}/z\n')
  assert register.default_dir('zsh', env) == '/h/z'
  assert register.default_dir('bash', env) == '/h/.local/share/bash-completion/completions'


def write_tool(path: Path, usage: str, mtime: int):
  """A program with a docopt --help, recording its argv otherwise"""
  path.parent.mkdir(parents=True, exist_ok=True)
  path.write_text(f'''#!{shutil.which('bash')}
if [[ $1 = --help ]]; then
  printf '%s\\n' {usage!r}
  exit 0
fi
printf '%s\\n' "$@" > "$DOCOPT_COMPLETION_OUT.tmp"
mv -f "$DOCOPT_COMPLETION_OUT.tmp" "$DOCOPT_COMPLETION_OUT"
''')
  path.chmod(0o755)
  os.utime(path, (mtime, mtime))


@pytest.fixture
def bin(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
  bindir = tmp_path / 'bin'
  bindir.mkdir()
  # docopt.completion for the refresh hook, running this checkout with the test's interpreter and imports
  pythonpath = os.pathsep.join([str(Path(__file__).parent.parent)] + [p for p in sys.path if p])
  wrapper = bindir / 'docopt.completion'
  wrapper.write_text(
    f'#!{shutil.which("sh")}\nPYTHONPATH={pythonpath} exec {sys.executable} -m docopt_completion "$@"\n'
  )
  wrapper.chmod(0o755)
  monkeypatch.setenv('PATH', f'{bindir}{os.pathsep}{os.environ["PATH"]}')
  return bindir


def test_register_stamps_the_script(bin: Path, tmp_path: Path):
  write_tool(bin / 'tool', 'Usage: tool alpha', 1000000000)
  path = register.register('bash', 'tool', str(tmp_path / 'out'))
  assert path == str(tmp_path / 'out' / 'tool.bash')
  assert os.stat(path).st_mtime_ns == os.stat(bin / 'tool').st_mtime_ns
  assert 'alpha' in Path(path).read_text()


def test_path_is_named_by_the_usage(bin: Path, tmp_path: Path):
  # Like a script run through a symlink without the extension
  write_tool(tmp_path / 'src' / 'tool.sh', 'Usage: tool alpha', 1000000000)
  path = register.register('zsh', str(tmp_path / 'src' / 'tool.sh'), str(tmp_path / 'out'))
  assert path == str(tmp_path / 'out' / '_tool')
  assert 'compdef _tool tool' in Path(path).read_text()


def test_gnu_help_is_rejected(bin: Path, tmp_path: Path):
  write_tool(bin / 'tool', 'Usage: tool [OPTION]... FILE...', 1000000000)
  with pytest.raises(register.NotDocoptError):
    register.register('zsh', 'tool', str(tmp_path / 'out'))
  assert not (tmp_path / 'out').exists()


def test_missing_command(bin: Path, tmp_path: Path):
  with pytest.raises(docopt_parser.DocoptError):
    register.register('bash', 'no-such-tool', str(tmp_path / 'out'))


@pytest.mark.parametrize('shell', ['bash', 'zsh'])
@pytest.mark.parametrize('change', ['mtime', 'path'])
def test_refresh(bin: Path, tmp_path: Path, shell: str, change: str):
  tool = bin / 'tool'
  if change == 'path':
    # Like a NixOS upgrade: a new store path, both with the same mtime
    write_tool(tmp_path / 'v1' / 'tool', 'Usage: tool alpha', 1)
    write_tool(tmp_path / 'v2' / 'tool', 'Usage: tool (alpha|beta)', 1)
    tool.symlink_to(tmp_path / 'v1' / 'tool')
  else:
    write_tool(tool, 'Usage: tool alpha', 1000000000)
  out = tmp_path / 'out'
  path = register.register(shell, 'tool', str(out))
  if shell == 'bash':
    session = Shell(['bash', '--norc', '--noprofile', '-i'], f'source {path}')
  else:
    session = Shell(['zsh', '-f', '-i'], f'''
fpath=({out} $fpath)
autoload -U compinit && compinit -u -d "$HOME/.zcompdump"
''')
  try:
    assert session.run('tool b\t') == ['b']
    if change == 'path':
      tool.unlink()
      tool.symlink_to(tmp_path / 'v2' / 'tool')
    else:
      write_tool(tool, 'Usage: tool (alpha|beta)', 1000000100)
    assert session.run('tool b\t') == ['beta']
    assert session.run('tool a\t') == ['alpha']
  finally:
    session.close()
  assert os.stat(path).st_mtime_ns == os.stat(os.path.realpath(tool)).st_mtime_ns
  assert 'beta' in Path(path).read_text()


@pytest.mark.parametrize('shell', ['bash', 'zsh'])
def test_refresh_by_path(bin: Path, tmp_path: Path, shell: str):
  # A repo that tracks its task and the completion, cloned elsewhere
  write_tool(tmp_path / 'repo' / 'tasks' / 'tool.sh', 'Usage: tool alpha', 1000000000)
  path = register.register(shell, str(tmp_path / 'repo' / 'tasks' / 'tool.sh'), str(tmp_path / 'repo' / 'completions'))
  assert str(tmp_path) not in Path(path).read_text()
  shutil.copytree(tmp_path / 'repo', tmp_path / 'clone')
  name = Path(path).name
  path = str(tmp_path / 'clone' / 'completions' / name)
  # To run it, the completion doesn't look it up
  (bin / 'tool').symlink_to(tmp_path / 'clone' / 'tasks' / 'tool.sh')
  if shell == 'bash':
    session = Shell(['bash', '--norc', '--noprofile', '-i'], f'source {path}')
  else:
    session = Shell(['zsh', '-f', '-i'], f'autoload -U compinit && compinit -u -d "$HOME/.zcompdump"\nsource {path}')
  try:
    assert session.run('tool b\t') == ['b']
    write_tool(tmp_path / 'clone' / 'tasks' / 'tool.sh', 'Usage: tool (alpha|beta)', 1000000100)
    assert session.run('tool b\t') == ['beta']
  finally:
    session.close()
  assert os.stat(path).st_mtime_ns == os.stat(tmp_path / 'clone' / 'tasks' / 'tool.sh').st_mtime_ns
  assert 'beta' in Path(path).read_text()
  assert 'beta' not in (tmp_path / 'repo' / 'completions' / name).read_text()
