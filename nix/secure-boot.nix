{ config, lib, pkgs, ... }:
let
  kernel = config.boot.kernelPackages.kernel;
  modulesTree = config.system.modulesTree;
  image = config.boot.kernelPackages.rebuildImage { inherit modulesTree; };
  certificates = pkgs.runCommand "glf-module-certificates" { } ''
    mkdir -p "$out"
    cp ${modulesTree}/lib/modules/${kernel.modDirVersion}/modules.cer "$out/modules.cer"
    test -s "$out/modules.cer"
    sha256sum "$out/modules.cer" | cut -d' ' -f1 > "$out/bundle.sha256"
  '';
in {
  config = {
    system.build.glfKernel = image;
    system.build.glfCertificates = certificates;
    boot.kernelPatches = [{
      name = "glf-module-enforcement";
      patch = null;
      structuredExtraConfig = with lib.kernel; {
        MODULE_SIG = lib.mkForce yes;
        MODULE_SIG_ALL = lib.mkForce yes;
        MODULE_SIG_FORCE = lib.mkForce yes;
        SECURITY_LOCKDOWN_LSM = lib.mkForce yes;
        SECURITY_LOCKDOWN_LSM_EARLY = lib.mkForce yes;
        LOCK_DOWN_KERNEL_FORCE_INTEGRITY = lib.mkForce yes;
      };
    }];
    # rebuildImage injecte les certificats de tous les modules selectionnes
    # apres leur compilation, sans boucle noyau -> modules -> noyau.
    boot.uki.settings.UKI.Linux = "${image}/${config.system.boot.loader.kernelFile}";
    boot.uki.name = lib.mkDefault "glf-os";
  };
}
