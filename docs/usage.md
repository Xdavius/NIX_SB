# Utiliser le noyau et les drivers

## Choisir le noyau dans NIX_SB

`kernel.json` contient `{"package": "linuxPackages_6_18"}`. Changer cet attribut
pour choisir une autre famille disponible dans le nixpkgs du dépôt. Le patchlevel
exact dépend du nixpkgs fourni par les channels GLF-OS. La CI NIX_SB doit
reprendre cette révision. Son lock interne ne définit pas les versions GLF-OS.
Le noyau choisi doit prendre en charge kmodigest et rebuildImage.

## Consommer l’ensemble

```nix
let
  # pkgs provient des channels GLF-OS ; la CI doit utiliser le meme socle.
  sb = pkgs.callPackage sourceNixSb { signedReleaseFile = ./release.json; };
in {
  boot.kernelPackages = sb.kernelPackages;
  boot.extraModulePackages = [ sb.drivers.hid-fanatecff ];
}
```

Exemple documentaire uniquement, sans modification GLF-OS. La configuration
complète doit ajouter les paramètres de vérification et l’installation depuis
la publication signée décrits dans integration-glfos.md à la racine. L’initrd et le matériel restent propres au poste.

Pour GLF-OS, référencer NIX_SB comme source `flake = false` dans la sous-flake
`glf-apps`, puis appeler `default.nix` avec `callPackage` dans son overlay.
Les modules utilisent `pkgs.glf-kernel-center` ; ils n’importent pas la flake NIX_SB.
`channels-glfos` reste responsable de nixpkgs et nixpkgs-unstable par version.
L’import ne télécharge pas un autre nixpkgs et ne lit pas le lock NIX_SB.
Voir [l’intégration glf-apps](../integration-glfos.md) et la limite actuelle
de compatibilité : les pins actuels des channels ne fournissent pas rebuildImage.

`sb.kernelPackages.kernel` est le noyau de base pour l’initrd et les modules.
`sb.kernel` est uniquement son image enrichie, à comparer au noyau signé de la publication.
`sb.certificates` contient modules.cer, bundle.sha256 et approved-modules.json.
Les définitions individuelles restent importables avec callPackage ; pour un
driver, utiliser `sb.kernelPackages.callPackage` afin de garder le même noyau.

`sb.boot-tools` fournit glf-secureboot-install, sans réseau ni signature locale.
Avec signedReleaseFile, sb.signed expose bundle, kernel et bootloader.
Voir [le guide complet](../integration-glfos.md) pour les métadonnées v2.
La flake propose aussi base-kernel, kernel, certificates, modules-tree et les
paquets de drivers. Les sorties uki et enrollment restent des artefacts de test.

## NVIDIA

NIX_SB expose `sb.nvidia` (paquet complet) et `sb.drivers.nvidia-open` (modules).
La version et ses hashes sont choisis dans pkgs/drivers/nvidia/version.json.
Le consommateur utilise `hardware.nvidia.package = sb.nvidia;` et
`hardware.nvidia.open = true;` lorsque NVIDIA est activé. Il conserve la gestion
matérielle de PRIME, des services et de l’énergie. Cet exemple ne modifie pas GLF-OS.
Le nixpkgs fourni à callPackage doit autoriser les composants NVIDIA non libres.
