{
  description = "GLF-OS: noyau de confiance et UKI non signee pour signature CI";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

  outputs = { self, nixpkgs }: let
    system = "x86_64-linux";
    pkgs = import nixpkgs { inherit system; };
    # Machine fictive pour la CI uniquement. Les postes GLF importent le module
    # secureBoot dans leur propre nixosConfigurations."GLF-OS".
    target = nixpkgs.lib.nixosSystem {
      inherit system;
      specialArgs = { inputs = self.inputs; };
      modules = [ ./nix/secure-boot.nix ./tests/fixtures/machine.nix ];
    };
  in {
    nixosModules.secureBoot = import ./nix/secure-boot.nix;
    nixosModules.default = self.nixosModules.secureBoot;
    nixosConfigurations.prototype = target;
    packages.${system} = {
      kernel = target.config.system.build.glfKernel;
      uki = target.config.system.build.uki;
      certificates = target.config.system.build.glfCertificates;
      default = self.packages.${system}.uki;
    };
    devShells.${system}.ci = pkgs.mkShell {
      packages = with pkgs; [ bash coreutils openssl sbsigntool jq shellcheck python3 actionlint ];
      GLF_TEST_STUB = "${pkgs.systemd}/lib/systemd/boot/efi/linuxx64.efi.stub";
    };
  };
}
