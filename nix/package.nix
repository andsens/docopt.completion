{
  lib,
  python3Packages,
  fetchPypi,
  bash,
  zsh,
}:
let
  py = python3Packages;
  parsec = py.buildPythonPackage rec {
    pname = "parsec";
    version = "3.13";
    pyproject = true;
    build-system = [ py.setuptools ];
    src = fetchPypi {
      inherit pname version;
      hash = "sha256-lQFJywkyyM7883i+ELaNhk/qcLv+9c6Z/VisLzJYv5w=";
    };
    doCheck = false;
  };
  termcolor = py.buildPythonPackage rec {
    pname = "termcolor";
    version = "1.1.0";
    pyproject = true;
    build-system = [ py.setuptools ];
    src = fetchPypi {
      inherit pname version;
      hash = "sha256-HW1pzmYhEUOAP7xWZStB1ztKQAookde/ehzfTALeYTs=";
    };
  };
  flake8-pyproject = py.buildPythonPackage rec {
    pname = "flake8-pyproject";
    version = "1.2.4";
    format = "wheel";
    src = fetchPypi {
      inherit version format;
      pname = "flake8_pyproject";
      python = "py3";
      dist = "py3";
      hash = "sha256-6jTAV/mpMpx22Ycjuyu0mMxrqP+YcsTRmTLUjJEkmnc=";
    };
    dependencies = [ py.flake8 ];
  };
  docopt-parser = py.buildPythonPackage rec {
    pname = "docopt-parser";
    version = "0.0.1";
    format = "wheel";
    src = fetchPypi {
      inherit version format;
      pname = "docopt_parser";
      python = "py3";
      dist = "py3";
      hash = "sha256-bnG+k9ts3eeQ7bBU8vxGSoXAEioDtXuV9osP5ParHT8=";
    };
    # flake8-pyproject is a runtime dependency in docopt-parser 0.0.1's metadata
    dependencies = [
      py.docopt
      termcolor
      flake8-pyproject
      parsec
      py.pyyaml
      py.ordered-set
    ];
  };
in
py.buildPythonApplication {
  pname = "docopt-completion";
  version = "0.0.0-dev";
  pyproject = true;
  src = lib.fileset.toSource {
    root = ../.;
    fileset = lib.fileset.unions [
      ../docopt_completion
      ../tests
      ../docs
      ../pyproject.toml
    ];
  };
  build-system = [ py.poetry-core ];
  dependencies = [
    py.docopt
    termcolor
    py.pyyaml
    docopt-parser
  ];
  # The tests drive interactive bash and zsh sessions
  nativeCheckInputs = [
    py.pytestCheckHook
    bash
    zsh
  ];
  meta = {
    description = "Shell completion generated from docopt help texts";
    homepage = "https://github.com/andsens/docopt.completion";
    license = lib.licenses.mit;
    mainProgram = "docopt.completion";
  };
}
