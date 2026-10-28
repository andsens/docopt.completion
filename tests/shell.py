"""
Drives an interactive shell in a pty, so completion runs through the shell's own line editor.
The completion function under test writes its result to $DOCOPT_COMPLETION_OUT.tmp and renames
it to $DOCOPT_COMPLETION_OUT when done.
"""
import os
import pty
import select
import subprocess
import tempfile
import time
import typing as T


class Shell(object):
  def __init__(self, argv: T.List[str], setup: str, env: "T.Dict[str, str] | None" = None):
    super().__init__()
    self.tmp = tempfile.TemporaryDirectory()
    self.out = os.path.join(self.tmp.name, 'out')
    self.master, slave = pty.openpty()
    self.process = subprocess.Popen(
      argv, stdin=slave, stdout=slave, stderr=slave, cwd=self.tmp.name, start_new_session=True,
      env={
        'PATH': os.environ['PATH'], 'HOME': self.tmp.name, 'TERM': 'dumb',
        'DOCOPT_COMPLETION_OUT': self.out, **(env or {}),
      },
    )
    os.close(slave)
    setup_file = os.path.join(self.tmp.name, 'setup')
    with open(setup_file, 'w') as handle:
      handle.write(setup + f'\n: > {self.out}.ready\n')
    self.send(f'. {setup_file}\n')
    self.wait_for(self.out + '.ready')

  def send(self, text: str):
    os.write(self.master, text.encode())

  def drain(self):
    while select.select([self.master], [], [], 0)[0]:
      try:
        os.read(self.master, 65536)
      except OSError:
        return

  def wait_for(self, path: str, timeout: float = 5):
    deadline = time.monotonic() + timeout
    while not os.path.exists(path):
      self.drain()
      if time.monotonic() > deadline:
        raise TimeoutError(f'{path} did not appear')
      time.sleep(0.005)

  def complete(self, line: str) -> T.List[str]:
    """Type `line`, press tab and return what the completion function wrote, one item per line"""
    if os.path.exists(self.out):
      os.unlink(self.out)
    self.send(line + '\t')
    self.wait_for(self.out)
    with open(self.out) as handle:
      result = handle.read().split('\n')[:-1]
    # Clear the line, readline and zle both bind ^U to kill the line
    self.send('\x15')
    self.drain()
    return result

  def run(self, keys: str) -> T.List[str]:
    """Type `keys` (tabs included), press enter and return what the command wrote, one item per line"""
    if os.path.exists(self.out):
      os.unlink(self.out)
    self.send(keys)
    time.sleep(0.1)
    self.send('\n')
    self.wait_for(self.out)
    with open(self.out) as handle:
      return handle.read().split('\n')[:-1]

  def screen(self, keys: str, timeout: float = 0.5) -> str:
    """Type `keys`, return the terminal output until it has been quiet for `timeout` and clear the line"""
    self.drain()
    self.send(keys)
    output = b''
    while select.select([self.master], [], [], timeout)[0]:
      output += os.read(self.master, 65536)
    self.send('\x15')
    self.drain()
    return output.decode(errors='replace')

  def close(self):
    self.process.kill()
    self.process.wait()
    os.close(self.master)
    self.tmp.cleanup()
