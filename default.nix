{ pkgs, catalogueFile ? ./pkgs/drivers/catalogue.json }:
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
in {
  inherit kernelPackages drivers modulesTree;
  nvidia = kernelPackages.callPackage ./pkgs/drivers/nvidia/package.nix {};
  kernel = callPackage ./pkgs/kernel shared;
  certificates = callPackage ./pkgs/certificates shared;
  boot-tools = callPackage ./pkgs/boot-tools {};
  rocky-shim = callPackage ./pkgs/rocky-shim {};
}
