"""
docopt.completion - A completion script generator for docopt compatible help texts.
"""
import importlib.metadata

try:
  __version__ = importlib.metadata.version('docopt-completion')
except importlib.metadata.PackageNotFoundError:
  __version__ = '0.0.0-dev'

__all__ = []
