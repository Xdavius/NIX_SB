# A ajouter aux modules de la machine GLF-OS evaluee avec nixpkgs unstable.
# Le module glfBoot doit deja etre reexporte/importe par la flake GLF-OS.
{ ... }: {
  glf.boot = {
    enable = true;
    signing.github = {
      repository = "Xdavius/NIX_SB";
      ref = "main";
      tokenFile = "/run/credentials/glf-github-token";
      # Ce depot est public. Ne passer a true que si les images du poste peuvent
      # etre publiees (sinon utiliser un depot prive avec le meme service).
      allowPublicArtifacts = false;
    };
  };
  boot.loader.systemd-boot.enable = true;
  boot.loader.grub.enable = false;
  # Conserver les definitions materielles/ESP existantes de la machine.
}
