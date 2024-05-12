{ sources ? import ./sources.nix
, pkgs ? import sources.nixpkgs { }
}:

with pkgs;

buildEnv {
  name = "builder";
  paths = [
    elixir
  ];
}
