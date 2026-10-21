{ config, lib, pkgs, ... }:
let
  cfg = config.glf.boot;
  tools = pkgs.callPackage ./tools.nix { };
  rockyShim = pkgs.callPackage ./rocky-shim.nix { };
  kernel = config.boot.kernelPackages.kernel;
  modulesTree = config.system.modulesTree;
  image = config.boot.kernelPackages.rebuildImage { inherit modulesTree; };
  certificates = pkgs.runCommand "glf-module-certificates" { } ''
    mkdir -p "$out"
    cp ${modulesTree}/lib/modules/${kernel.modDirVersion}/modules.cer "$out/modules.cer"
    test -s "$out/modules.cer"
    sha256sum "$out/modules.cer" | cut -d' ' -f1 > "$out/bundle.sha256"
  '';
  metadata = pkgs.writeText "glf-boot.json" (builtins.toJSON {
    version = 1;
    kernel = "${image}/${config.system.boot.loader.kernelFile}";
    initrd = "${config.system.build.initialRamdisk}/${config.system.boot.loader.initrdFile}";
    stub = "${config.systemd.package}/lib/systemd/boot/efi/linuxx64.efi.stub";
    systemdBoot = "${config.systemd.package}/lib/systemd/boot/efi/systemd-bootx64.efi";
    ukify = "${pkgs.systemdUkify}/lib/systemd/ukify";
    kernelVersion = kernel.modDirVersion;
    kernelParams = config.boot.kernelParams;
  });
  installerConfig = pkgs.writeText "glf-installer.json" (builtins.toJSON {
    esp = config.boot.loader.efi.efiSysMountPoint;
    certificate = toString cfg.signing.certificate;
    shim = "${rockyShim}/share/efi";
    githubSigner = "${tools}/bin/glf-github-sign";
    inherit (cfg.signing.github) repository ref tokenFile allowPublicArtifacts;
    signingTimeout = cfg.signing.github.timeout;
    timeout = if config.boot.loader.timeout == null then "menu-force" else toString config.boot.loader.timeout;
    canTouchEfiVariables = config.boot.loader.efi.canTouchEfiVariables;
  });
in {
  options.glf.boot = {
    enable = lib.mkEnableOption "la chaine shim Rocky -> systemd-boot -> UKI avec signature distante";
    install.enable = lib.mkOption {
      type = lib.types.bool;
      default = true;
      description = "Raccorder l'installation signee a nixos-rebuild boot/switch (et glf-update).";
    };
    signing.certificate = lib.mkOption {
      type = lib.types.path;
      default = ../certificates/GLF-TEST.pem;
      description = "Certificat public PEM attendu du service GitHub. Le certificat fourni est reserve aux tests.";
    };
    signing.github = {
      repository = lib.mkOption { type = lib.types.str; default = "Xdavius/NIX_SB"; };
      ref = lib.mkOption { type = lib.types.str; default = "main"; };
      tokenFile = lib.mkOption {
        type = lib.types.nullOr lib.types.str;
        default = null;
        description = "Chemin runtime du jeton GitHub, jamais une valeur Nix de type path. Sinon utiliser l'auth gh du compte root.";
      };
      allowPublicArtifacts = lib.mkOption {
        type = lib.types.bool; default = false;
        description = "Autoriser explicitement la publication des images de cette machine comme artefacts d'un depot public.";
      };
      timeout = lib.mkOption { type = lib.types.ints.positive; default = 3600; };
    };
  };
  config = lib.mkIf cfg.enable {
    assertions = [
      { assertion = pkgs.stdenv.hostPlatform.system == "x86_64-linux"; message = "GLF Secure Boot supporte actuellement x86_64-linux uniquement."; }
      { assertion = config.boot.kernelPackages ? rebuildImage; message = "GLF Secure Boot exige nixpkgs unstable avec kmodigest et rebuildImage."; }
      { assertion = config.boot.initrd.secrets == { }; message = "Ne pas envoyer d'initrd contenant boot.initrd.secrets au signataire distant."; }
      { assertion = config.boot.loader.systemd-boot.xbootldrMountPoint == null; message = "GLF Secure Boot utilise une seule ESP ; XBOOTLDR n'est pas encore pris en charge."; }
      { assertion = config.specialisation == { }; message = "GLF Secure Boot : les specialisations ne sont pas encore prises en charge."; }
      { assertion = !config.boot.loader.grub.enable; message = "GLF Secure Boot utilise systemd-boot ; desactiver GRUB."; }
    ];
    system.build.glfKernel = image;
    system.build.glfCertificates = certificates;
    system.build.glfBootMetadata = metadata;
    system.build.glfInstallerConfig = installerConfig;
    system.build.glfSystemdBoot = pkgs.runCommand "glf-systemd-boot-unsigned" { } ''
      mkdir -p "$out"
      cp ${config.systemd.package}/lib/systemd/boot/efi/systemd-bootx64.efi "$out/systemd-bootx64.efi"
    '';
    # Nixpkgs signe deja les modules avec kmodigest. Ces parametres sont
    # embarques dans l'UKI signee et imposent la verification au demarrage.
    boot.kernelParams = [ "module.sig_enforce=1" "lockdown=integrity" ];
    boot.loader.systemd-boot.enable = true;
    boot.loader.systemd-boot.editor = false;
    boot.loader.supportsInitrdSecrets = lib.mkForce false;
    systemd.services.systemd-boot-update.enable = false;
    environment.systemPackages = [ tools pkgs.mokutil ];
    # Aucun lien vers l'UKI ici : celle-ci contient deja la reference au toplevel.
    system.systemBuilderCommands = ''
      ln -s ${metadata} "$out/glf-boot.json"
    '';
    system.build.installBootLoader = lib.mkIf cfg.install.enable (lib.mkForce (
      pkgs.writeShellScript "install-glf-boot" ''
        exec ${tools}/bin/glf-install-boot --config ${installerConfig} "$@"
      ''
    ));
    # rebuildImage injecte les certificats de tous les modules selectionnes
    # apres leur compilation, sans boucle noyau -> modules -> noyau.
    boot.uki.settings.UKI.Linux = "${image}/${config.system.boot.loader.kernelFile}";
    boot.uki.name = lib.mkDefault "glf-os";
  };
}
