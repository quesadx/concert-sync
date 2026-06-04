{
  description = "Python Development Environment";

  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/nixos-unstable";
  };

  outputs =
    { self, nixpkgs }:
    let
      system = "x86_64-linux";
      pkgs = nixpkgs.legacyPackages.${system};
    in
    {
      devShells.${system}.default = pkgs.mkShell {
        buildInputs = with pkgs; [
          python314
          uv
          python314Packages.pytest
          python314Packages.black
          python314Packages.flake8
          python314Packages.textual
          opencode
          gsd
          pnpm
        ];
        shellHook = ''
          export LD_LIBRARY_PATH=${libPath}:$LD_LIBRARY_PATH
          export NPM_CONFIG_PREFIX=$PWD/.npm-global
          export PATH=$PWD/.npm-global/bin:$PATH

          # Auto-verify or install the gsd-sdk locally into this shell's pathway
          if [ ! -d "$PWD/.npm-global/lib/node_modules/get-shit-done-cc" ]; then
            echo "Installing GSD SDK for OpenCode subagents..."
            npm install -g get-shit-done-cc
          fi
        '';
      };
    };
}
