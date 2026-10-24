{ config, lib, pkgs, ... }:
let
  cfg = config.glf.multiboot;
  sb = config.glf.secureboot.packageSet;
  installConfig = pkgs.writeText "glf-secureboot-install.json" (builtins.toJSON {
    esp = config.boot.loader.efi.efiSysMountPoint;
    certificate = "${sb.secureboot-certificate}/share/secureboot/GLF.pem";
    timeout = toString cfg.timeout;
    canTouchEfiVariables = config.boot.loader.efi.canTouchEfiVariables;
    installFallback = cfg.installFallback;
    multiboot = { inherit (cfg) enable makeDefault configurationLimit; };
  });
  metadata = pkgs.writeText "glf-secureboot.json" (builtins.toJSON {
    version = 2;
    signedBundle = "${sb.signed.bundle}";
    kernel = "${sb.kernel}/bzImage";
    initrd = "${config.system.build.initialRamdisk}/${config.system.boot.loader.initrdFile}";
    kernelParams = config.boot.kernelParams;
  });
in {
  options.glf = {
    secureboot = {
      enable = (lib.mkEnableOption "le demarrage signe GLF publie par NIX_SB") // { default = true; };
      packageSet = lib.mkOption {
        type = lib.types.raw;
        default = pkgs.glf-kernel-center;
        description = "Ensemble NIX_SB fourni par glf-apps avec signedReleaseFile.";
      };
    };
    multiboot = {
      enable = lib.mkEnableOption "le menu multiboot rEFInd GLF";
      makeDefault = lib.mkOption { type = lib.types.bool; default = true; };
      timeout = lib.mkOption { type = lib.types.ints.unsigned; default = 10; };
      configurationLimit = lib.mkOption { type = lib.types.ints.positive; default = 10; };
      installFallback = lib.mkOption {
        type = lib.types.bool;
        default = !config.boot.loader.efi.canTouchEfiVariables;
        description = "Installer aussi EFI/BOOT. Un chemin existant non gere par GLF est refuse en mode multiboot.";
      };
    };
  };
  config = lib.mkMerge [
    (lib.mkIf config.glf.secureboot.enable {
      assertions = [
        { assertion = pkgs.stdenv.hostPlatform.isx86_64; message = "GLF multiboot exige x86_64 UEFI."; }
        { assertion = sb.signed != null; message = "GLF Secure Boot exige signedReleaseFile."; }
        { assertion = !(config.boot.lanzaboote.enable or false); message = "Desactiver Lanzaboote pour utiliser les composants signes GLF."; }
      ];
      boot.kernelPackages = sb.kernelPackages;
      boot.kernelParams = [ "module.sig_enforce=1" "lockdown=integrity" ];
      boot.loader.grub.enable = lib.mkForce false;
      boot.loader.systemd-boot.enable = lib.mkForce false;
      boot.loader.external = {
        enable = true;
        installHook = pkgs.writeShellScript "glf-install-boot" ''
          exec ${sb.boot-tools}/bin/glf-secureboot-install --config ${installConfig} "$1"
        '';
      };
      environment.systemPackages = [ sb.boot-tools ];
      environment.etc."secureboot/install.json".source = installConfig;
      environment.etc."secureboot/GLF.pem".source = "${sb.secureboot-certificate}/share/secureboot/GLF.pem";
      environment.etc."secureboot/GLF.cer".source = "${sb.secureboot-certificate}/share/secureboot/GLF.cer";
      system.systemBuilderCommands = lib.mkAfter ''
        ln -s ${metadata} "$out/glf-secureboot.json"
      '';
    })
  ];
}
