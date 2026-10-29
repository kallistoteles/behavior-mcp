{
  description = "Behavior MCP released public API development and quality environment";
  inputs.nixpkgs.url = "github:NixOS/nixpkgs/293d6abedf0478e681a4dfcfcb35b30fc796a32f";
  inputs.behavior-proof.url = "github:kallistoteles/behavior-ir/1cba9e16ff73f927ae08e70a7bc74a6ca52355e4";
  outputs = { self, nixpkgs, behavior-proof }: let
    system = "x86_64-linux";
    pkgs = import nixpkgs { inherit system; };
    proof = behavior-proof.packages.${system}.safety-proof-toolchain;
  in {
    devShells.${system}.default = pkgs.mkShell {
      packages = [ pkgs.python313 pkgs.uv pkgs.ruff pkgs.z3 ];
      UV_PYTHON = "${pkgs.python313}/bin/python3.13";
      UV_PYTHON_DOWNLOADS = "never";
      BEHAVIOR_SAFETY_TOOLCHAIN = "${proof}";
      BEHAVIOR_SAFETY_TOOLCHAIN_DRV = builtins.unsafeDiscardStringContext proof.drvPath;
    };
  };
}
