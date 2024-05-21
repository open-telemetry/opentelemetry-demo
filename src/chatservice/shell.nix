with import <nixpkgs> {};
let
  basePackages = [
    gnumake
    gcc
    curl
    elixir
    inotify-tools
  ];
  
  inputs = if pkgs.system == "x86_64-darwin" then
    basePackages ++ [ pkgs.darwin.apple_skd.frameworks.CoreServices ]
  else
    basePackages;

  hooks = ''
    mkdir -p .nix-mix
    mkdir -p .nix-hex
    export MIX_HOME=$PWD/.nix-mix
    export HEX_HOME=$PWD/.nix-hex
    export PATH=$MIX_HOME/bin:$PATH
    export PATH=$HEX_HOME/bin:$PATH
    export LANG=en_US.UTF-8
  '';
in mkShell {
  buildInputs = inputs ++ [
    otel-desktop-viewer
  ];
  
  shellHook = hooks;
}
