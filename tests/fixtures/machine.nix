# Machine fictive pour tester la CI, jamais une configuration de poste GLF-OS.
# La vraie machine conserve ses fichiers /etc/nixos et sa configuration materielle.
{ ... }: {
  glf.boot.enable = true;
  boot.uki.version = "prototype";
  networking.hostName = "glf-uki-prototype";
  fileSystems."/" = {
    device = "/dev/disk/by-label/GLF_ROOT";
    fsType = "ext4";
  };
  boot.initrd.availableKernelModules = [ "virtio_pci" "virtio_blk" "virtio_scsi" ];
  boot.loader.grub.enable = false;
  # Pas d'installation de chargeur sur la machine de build.
  system.stateVersion = "26.05";
}
