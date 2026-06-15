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
            python314Packages.pyside6
            uv

            nodejs
            pnpm

            opencode
            gsd
          ];

          shellHook = ''
            export NPM_CONFIG_PREFIX="$PWD/.npm-global"
            export PATH="$PWD/.npm-global/bin:$PATH"

            GSD_MARKER="$PWD/.gsd-installed"

            if [ ! -f "$GSD_MARKER" ]; then
              echo "Installing GSD for OpenCode..."

              npx -y @opengsd/gsd-core@latest install \
                --ide opencode \
                --project .

              touch "$GSD_MARKER"
            fi
          '';
        };
      }
    );
}
