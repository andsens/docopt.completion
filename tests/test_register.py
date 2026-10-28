import os
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


def write_tool(path: Path, usage: str, mtime: int):
  """A program with a docopt --help, recording its argv otherwise"""
  path.parent.mkdir(parents=True, exist_ok=True)
  path.write_text(f'''#!/usr/bin/env bash
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
  # docopt-completion for the refresh hook, running this checkout
  pythonpath = os.pathsep.join([
    str(Path(__file__).parent.parent), os.path.dirname(os.path.dirname(docopt_parser.__file__)),
  ])
  wrapper = bindir / 'docopt-completion'
  wrapper.write_text(f'#!/bin/sh\nPYTHONPATH={pythonpath} exec {sys.executable} -m docopt_completion "$@"\n')
  wrapper.chmod(0o755)
  monkeypatch.setenv('PATH', f'{bindir}{os.pathsep}{os.environ["PATH"]}')
  return bindir


def test_register_stamps_the_script(bin: Path, tmp_path: Path):
  write_tool(bin / 'tool', 'Usage: tool alpha', 1000000000)
  path = register.register('bash', 'tool', str(tmp_path / 'out'))
  assert path == str(tmp_path / 'out' / 'tool.bash')
  assert os.stat(path).st_mtime_ns == os.stat(bin / 'tool').st_mtime_ns
  assert 'alpha' in Path(path).read_text()


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
