"""
docopt.completion - A completion script generator for docopt compatible help texts.
"""

__version__: str
try:
  from .version import __version__  # type: ignore
except ImportError:
  __version__ = '0.0.0-dev'

__all__ = []
