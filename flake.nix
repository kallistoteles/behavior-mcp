{
  description = "Behavior MCP released public API development and quality environment";
  inputs.nixpkgs.url = "github:NixOS/nixpkgs/293d6abedf0478e681a4dfcfcb35b30fc796a32f";
  outputs = { self, nixpkgs }: let
    system = "x86_64-linux";
    pkgs = import nixpkgs { inherit system; };
  in {
    devShells.${system}.default = pkgs.mkShell {
      packages = [ pkgs.python313 pkgs.uv pkgs.ruff pkgs.z3 ];
      UV_PYTHON = "${pkgs.python313}/bin/python3.13";
      UV_PYTHON_DOWNLOADS = "never";
    };
  };
}
