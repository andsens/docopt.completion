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


def generate(prog: str, compiled: Tb.Tables, refresh: "script.Refresh | None" = None) -> str:
  # Named like the file compinit autoloads (_<prog>), so that the first run replaces the autoload stub
  function = '_' + prog
  code = ''
  if refresh is not None:
    if isinstance(refresh, str):
      setup = f'local script=${{functions_source[{function}]}}\nlocal bin=${{script:h}}/{script.quote(refresh)}'
      check = '-e $bin && ( $bin -nt $script || $bin -ot $script )'
      regenerate, path = 'docopt.completion register --dir=${script:h} zsh $bin', '$script'
    else:
      binary, path, regenerate = (script.quote(refresh[0]), script.quote(refresh[1]), shlex.join(refresh[2]))
      setup = f'local bin=${{commands[{prog}]:A}}'
      check = f'-n $bin && ( $bin != {binary} || $bin -nt {path} || $bin -ot {path} )'
    code = f'''# Regenerate this script when {prog} changed since
{setup}
if [[ -z $_docopt_refreshed && {check} ]]; then
  local _docopt_refreshed=1
  if {regenerate} >/dev/null 2>&1; then
    source {path}
    {function} "$@"
    return
  fi
fi'''
  return script.render('zsh.sh', prog, function, compiled, source_code, 1, True, code)
