{
  description = "concert-sync flake for basic python";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs =
    {
      self,
      nixpkgs,
      flake-utils,
    }:
    flake-utils.lib.eachDefaultSystem (
      system:
      let
        pkgs = import nixpkgs { inherit system; };

        libPath = pkgs.lib.makeLibraryPath [
          pkgs.stdenv.cc.cc
        ];
      in
      {
        devShells.default = pkgs.mkShell {
          packages = with pkgs; [
            python314
            python314Packages.pytest
            python314Packages.black
            python314Packages.flake8
            python314Packages.textual

            nodejs
            pnpm

            opencode
            gsd
          ];

          shellHook = ''
            export LD_LIBRARY_PATH="${libPath}:$LD_LIBRARY_PATH"

            export NPM_CONFIG_PREFIX="$PWD/.npm-global"
            export PATH="$PWD/.npm-global/bin:$PATH"

            if [ ! -d "$PWD/.npm-global/lib/node_modules/get-shit-done-cc" ]; then
              echo "Installing GSD SDK for OpenCode subagents..."
              npm install -g get-shit-done-cc
            fi
          '';
        };
      }
    );
}
