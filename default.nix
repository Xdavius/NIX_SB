{ pkgs, catalogueFile ? ./pkgs/drivers/catalogue.json, signedReleaseFile ? null }:
let
  inherit (pkgs) callPackage;
  kernelPackages = import ./pkgs/kernel/select.nix { inherit pkgs; };
  drivers = builtins.removeAttrs (callPackage ./pkgs/drivers {
    inherit kernelPackages catalogueFile;
  }) [ "override" "overrideDerivation" ];
  modulesTree = callPackage ./pkgs/modules-tree {
    inherit kernelPackages;
    approvedModules = drivers;
  };
  shared = { inherit kernelPackages modulesTree; approvedModules = drivers; };
in rec {
  inherit kernelPackages drivers modulesTree;
  nvidia = kernelPackages.callPackage ./pkgs/drivers/nvidia/package.nix {};
  kernel = callPackage ./pkgs/kernel shared;
  certificates = callPackage ./pkgs/certificates shared;
  refind = callPackage ./pkgs/refind {};
  multiboot-assets = callPackage ./pkgs/multiboot-assets { inherit refind; };
  boot-tools = callPackage ./pkgs/boot-tools { multibootAssets = multiboot-assets; };
  nixosModule = ./modules/multiboot.nix;
  secureboot-certificate = callPackage ./pkgs/secureboot-certificate {};
  signed = if signedReleaseFile == null then null else callPackage ./pkgs/signed {
    inherit kernel refind;
    rockyShim = rocky-shim;
    releaseFile = signedReleaseFile;
  };
  rocky-shim = callPackage ./pkgs/rocky-shim {};
}
