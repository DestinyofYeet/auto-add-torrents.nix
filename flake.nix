{
  description = "Automatically fetch torrents from an rss feed and add them to deluge";

  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs?ref=nixos-unstable";
  };

  outputs = { self, nixpkgs } : 
  let 
    pkgs = import nixpkgs { system = "x86_64-linux"; };

    python = pkgs.python3;

    pythonPkgs = with python.pkgs; [
      deluge-client
      feedparser
      aiohttp
    ];
  in {
    devShells.x86_64-linux.default = pkgs.mkShell {
      nativeBuildInputs = [
        python
      ] ++ pythonPkgs;
    };

    # build with nix build
    packages.x86_64-linux.default = pkgs.python312Packages.buildPythonApplication {
      pname = "auto-add-torrents";
      version = "0.1.0";
      src = ./.;
      propagatedBuildInputs = pythonPkgs;
    };

    nixosModules.auto-add-torrents = import ./module.nix self;

    hydraJobs = {
      inherit (self) packages;
    };
  };
}
