{ self }:
{
  config,
  pkgs,
  lib,
  ...
}:
let
  cfg = config.programs.docopt-completion;
  inherit (lib) types mkOption;
  shell = name: {
    enable = lib.mkEnableOption "${name} completion for the commands";
    directory = mkOption {
      type = types.nullOr types.str;
      default = null;
      example = "$HOME/.zfunc";
      description = ''
        Where to write the ${name} completion scripts, expanded by the shell. `null` is
        `docopt.completion register`'s default.
      '';
    };
  };
  # The activation PATH is empty, the commands are looked up where the user's PATH would find them
  searchPath = lib.concatStringsSep ":" (
    [
      "${config.home.profileDirectory}/bin"
      "/run/current-system/sw/bin"
    ]
    ++ config.home.sessionPath
  );
  register =
    name:
    let
      dir = lib.optionalString (cfg.${name}.directory != null) ''--dir="${cfg.${name}.directory}" '';
    in
    lib.concatMapStrings (command: ''
      run ${lib.getExe cfg.package} register ${dir}${name} ${lib.escapeShellArg command} \
        || warnEcho "docopt.completion: Could not register ${name} completion for ${command}"
    '') cfg.commands;
in
{
  options.programs.docopt-completion = {
    enable = lib.mkEnableOption "shell completion for docopt programs";
    package = mkOption {
      type = types.package;
      default = self.packages.${pkgs.stdenv.hostPlatform.system}.default;
      defaultText = lib.literalExpression "docopt-completion.packages.\${system}.default";
      description = "The docopt-completion package.";
    };
    commands = mkOption {
      type = types.listOf types.str;
      default = [ ];
      example = [ "naval_fate" ];
      description = ''
        Commands to register completion for on activation, by name or path. Names are looked up in
        the profile, the system path and `home.sessionPath`. The scripts regenerate themselves when
        a command changes.
      '';
    };
    bash = shell "bash";
    zsh = shell "zsh";
  };

  config = lib.mkIf cfg.enable {
    # The scripts run docopt.completion from $PATH when they regenerate
    home.packages = [ cfg.package ];
    home.activation.docopt-completion = lib.hm.dag.entryAfter [ "writeBoundary" ] ''
      (
        export PATH="$PATH:${searchPath}"
        ${lib.optionalString cfg.bash.enable (register "bash")}
        ${lib.optionalString cfg.zsh.enable (register "zsh")}
      )
    '';
  };
}
