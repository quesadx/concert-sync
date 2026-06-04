{
  description = "concert-sync flake for basic python";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = import nixpkgs { inherit system; };
      in
      {
        devShells.default = pkgs.mkShell {
            packages = with pkgs; [
            python314
            python314Packages.pytest
            python314Packages.black
            python314Packages.flake8
            python314Packages.textual
            pnpm
          ];
        };
      });
}
