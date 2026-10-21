{
  description = "GLF-OS: noyau de confiance et UKI non signee pour signature CI";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

  outputs = { self, nixpkgs }: let
    system = "x86_64-linux";
    pkgs = import nixpkgs { inherit system; };
    rockyShim = pkgs.callPackage ./nix/rocky-shim.nix { };
    # Machine fictive pour la CI uniquement. Les postes GLF importent le module
    # secureBoot dans leur propre nixosConfigurations."GLF-OS".
    target = nixpkgs.lib.nixosSystem {
      inherit system;
      specialArgs = { inputs = self.inputs; };
      modules = [ ./nix/secure-boot.nix ./tests/fixtures/machine.nix ];
    };
  in {
    overlays.default = final: prev: {
      glf-boot-tools = final.callPackage ./nix/tools.nix { };
      glf-rocky-shim = final.callPackage ./nix/rocky-shim.nix { };
    };
    nixosModules.secureBoot = import ./nix/secure-boot.nix;
    nixosModules.default = self.nixosModules.secureBoot;
    nixosConfigurations.prototype = target;
    packages.${system} = {
      rocky-shim = rockyShim;
      glf-boot-tools = pkgs.callPackage ./nix/tools.nix { };
      systemd-boot = target.config.system.build.glfSystemdBoot;
      enrollment = pkgs.callPackage ./nix/enrollment.nix { inherit rockyShim; };
      kernel = target.config.system.build.glfKernel;
      uki = target.config.system.build.uki;
      certificates = target.config.system.build.glfCertificates;
      default = self.packages.${system}.uki;
    };
    checks.${system}.module-contract = import ./nix/module-contract.nix {
      inherit pkgs nixpkgs self target system;
    };
    devShells.${system} = {
    ci = pkgs.mkShell {
      packages = with pkgs; [ bash coreutils openssl sbsigntool jq shellcheck python3 actionlint binutils ];
      GLF_TEST_BOOT = "${pkgs.systemd}/lib/systemd/boot/efi/systemd-bootx64.efi";
      GLF_TEST_UKIFY = "${pkgs.systemdUkify}/lib/systemd/ukify";
      GLF_TEST_SHIM = "${rockyShim}/share/efi";
      GLF_TEST_STUB = "${pkgs.systemd}/lib/systemd/boot/efi/linuxx64.efi.stub";
    };
    vm = pkgs.mkShell {
      packages = with pkgs; [ python3 qemu_test python3Packages.virt-firmware
        openssl sbsigntool cpio gzip zstd dosfstools mtools coreutils ];
      GLF_VM_MODULES = "${target.config.system.modulesTree}";
      GLF_VM_FIRMWARE = "${pkgs.OVMFFull.fd}/FV";
      GLF_VM_BUSYBOX = "${pkgs.pkgsStatic.busybox}/bin/busybox";
      GLF_TEST_BOOT = "${pkgs.systemd}/lib/systemd/boot/efi/systemd-bootx64.efi";
      GLF_TEST_STUB = "${pkgs.systemd}/lib/systemd/boot/efi/linuxx64.efi.stub";
      GLF_TEST_UKIFY = "${pkgs.systemdUkify}/lib/systemd/ukify";
      GLF_TEST_SHIM = "${rockyShim}/share/efi";
    };
    };
  };
}
