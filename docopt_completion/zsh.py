import shlex
from docopt_completion import tables as Tb, script

compsys = {
  'files': '_files',
  'dirs': '_files -/',
  'hosts': '_hosts',
  'users': '_users',
  'groups': '_groups',
  'commands': '_command_names -e',
  'signals': '_signals',
  'processes': '_pids',
}


def source_code(source: Tb.Source) -> str:
  if isinstance(source, str):
    return f'{compsys[source]} && ret=0'
  if 'words' in source:
    return 'compadd -- ' + ' '.join(shlex.quote(str(word)) for word in source['words']) + ' && ret=0'
  return f'compadd -- ${{(f)"$({source["command"]})"}} && ret=0'


def generate(prog: str, compiled: Tb.Tables) -> str:
  # Named like the file compinit autoloads (_<prog>), so that the first run replaces the autoload stub
  return script.render('zsh.sh', prog, '_' + prog, compiled, source_code, 1, True)
