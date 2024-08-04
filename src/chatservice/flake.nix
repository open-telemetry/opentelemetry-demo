{
  description = "Development environment";

  inputs = {
    flake-utils = { url = "github:numtide/flake-utils"; };
  };

  outputs = { self, nixpkgs, flake-utils }:
   flake-utils.lib.eachDefaultSystem (system:
      let
        inherit (nixpkgs.lib) optional;
        pkgs = import nixpkgs { inherit system; };

        elixir = pkgs.beam.packages.erlang.elixir;
        elixir-ls = pkgs.beam.packages.erlang.elixir_ls;
        locales = pkgs.glibcLocales;

        hooks = ''
          mkdir -p .nix-mix
          mkdir -p .nix-hex
          export MIX_HOME=$PWD/.nix-mix
          export HEX_HOME=$PWD/.nix-hex
          export PATH=$MIX_HOME/bin:$PATH
          export PATH=$HEX_HOME/bin:$PATH
          export LANG=en_US.UTF-8
        '';
      in
      {
        devShell = pkgs.mkShell {
          buildInputs = [
            elixir
            locales
          ];

          shellHook = hooks;
        };
      });
}
