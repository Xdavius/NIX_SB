# Configuration fictive pour verifier le raccordement des paquets, sans installation.
{ sb, lib, ... }: {
  nixpkgs.config.allowUnfreePredicate = package:
    lib.hasPrefix "nvidia" (lib.getName package);
  boot.kernelPackages = sb.kernelPackages;
  boot.extraModulePackages = builtins.attrValues sb.drivers;
  boot.kernelParams = [ "module.sig_enforce=1" "lockdown=integrity" ];
  boot.uki.settings.UKI.Linux = "${sb.kernel}/bzImage";
  boot.uki.name = "glf-os";
  boot.uki.version = "prototype";
  boot.loader.systemd-boot.enable = true;
  boot.loader.systemd-boot.editor = false;
  boot.loader.grub.enable = false;
  networking.hostName = "glf-uki-prototype";
  fileSystems."/" = { device = "/dev/disk/by-label/GLF_ROOT"; fsType = "ext4"; };
  boot.initrd.availableKernelModules = [ "virtio_pci" "virtio_blk" "virtio_scsi" ];
  system.stateVersion = "26.05";
}
