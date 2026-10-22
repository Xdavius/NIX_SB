{
  description = "NIX_SB : paquets noyau de confiance, drivers et outils Secure Boot";
  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";


  outputs = { self, nixpkgs }:
    let
      system = "x86_64-linux";
      pkgs = import nixpkgs {
        inherit system;
        config.allowUnfreePredicate = package:
          nixpkgs.lib.hasPrefix "nvidia" (nixpkgs.lib.getName package);
      };
      sb = pkgs.callPackage ./default.nix {};
      target = nixpkgs.lib.nixosSystem {
        inherit system;
        specialArgs = { inherit sb; };
        modules = [ ./tests/fixtures/machine.nix ];
      };
      variantModules = excluded: pkgs.callPackage ./pkgs/modules-tree {
        inherit (sb) kernelPackages;
        approvedModules = builtins.removeAttrs sb.drivers [ excluded ];
      };
      testEnvironment = {
        GLF_TEST_BOOT = "${pkgs.systemd}/lib/systemd/boot/efi/systemd-bootx64.efi";
        GLF_TEST_STUB = "${pkgs.systemd}/lib/systemd/boot/efi/linuxx64.efi.stub";
        GLF_TEST_UKIFY = "${pkgs.systemdUkify}/lib/systemd/ukify";
        GLF_TEST_SHIM = "${sb.rocky-shim}/share/efi";
      };
    in {
      legacyPackages.${system} = sb;
      packages.${system} = {
        inherit (sb) kernel certificates boot-tools rocky-shim nvidia;
        base-kernel = sb.kernelPackages.kernel;
        modules-tree = sb.modulesTree;
        default = sb.kernel;
        uki = target.config.system.build.uki;
        systemd-boot = pkgs.runCommand "glf-systemd-boot-unsigned" {} ''
          mkdir -p "$out"
          cp ${pkgs.systemd}/lib/systemd/boot/efi/systemd-bootx64.efi "$out/"
        '';
        enrollment = pkgs.callPackage ./tests/fixtures/enrollment.nix { rockyShim = sb.rocky-shim; };
      } // sb.drivers;
      nixosConfigurations.prototype = target;
      checks.${system}.packages = import ./tests/packages.nix { inherit pkgs sb target; };
      devShells.${system} = {
        ci = pkgs.mkShell (testEnvironment // {
          packages = with pkgs; [ bash coreutils gh openssl sbsigntool jq shellcheck python3 actionlint binutils ];
        });
        vm = pkgs.mkShell (testEnvironment // {
          packages = with pkgs; [ python3 qemu_test python3Packages.virt-firmware
            openssl sbsigntool cpio gzip zstd dosfstools mtools coreutils kmod ];
          GLF_VM_MODULES = "${sb.modulesTree}";
          GLF_VM_MODULES_XONE = "${variantModules "xonedo"}";
          GLF_VM_MODULES_XONEDO = "${variantModules "xone"}";
          GLF_VM_FIRMWARE = "${pkgs.OVMFFull.fd}/FV";
          GLF_VM_BUSYBOX = "${pkgs.pkgsStatic.busybox}/bin/busybox";
        });
      };
    };
}
