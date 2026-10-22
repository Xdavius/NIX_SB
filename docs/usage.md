# Utiliser le noyau et les drivers

## Choisir le noyau dans NIX_SB

`kernel.json` contient `{"package": "linuxPackages_6_18"}`. Changer cet attribut
pour choisir une autre famille disponible dans le nixpkgs du dépôt. Le patchlevel
exact est fixé par `flake.lock`. Une mise à jour `nix flake update nixpkgs` est une
modification revue de l’ensemble noyau/drivers, pas une mise à jour indépendante
sur les postes. Le noyau doit prendre en charge kmodigest et rebuildImage.

## Consommer l’ensemble

```nix
let
  # pkgs doit provenir du nixpkgs verrouille par NIX_SB pour la signature CI.
  sb = pkgs.callPackage sourceNixSb {};
in {
  boot.kernelPackages = sb.kernelPackages;
  boot.extraModulePackages = [ sb.drivers.hid-fanatecff ];
  boot.uki.settings.UKI.Linux = "${sb.kernel}/bzImage";
}
```

Exemple documentaire uniquement, sans modification GLF-OS. La configuration
complète doit ajouter les paramètres de vérification, l’assemblage et la signature
décrits dans SIGNING-SERVICE.md. L’initrd et le matériel restent propres au poste.

Pour consommer exactement le noyau et les paquets approuvés sans réimporter
nixpkgs, la flake expose `inputs.nix-sb.legacyPackages.x86_64-linux`.
L’import via callPackage utilise le pkgs fourni ; il ne télécharge pas secrètement
un autre nixpkgs. Le consommateur doit donc suivre `inputs.nix-sb.inputs.nixpkgs`
ou une révision identique. Aucun noyau alternatif n’est un argument du point
d’entrée racine : le choix se fait dans kernel.json.

`sb.kernelPackages.kernel` est le noyau de base pour l’initrd et les modules.
`sb.kernel` est uniquement son image enrichie, à utiliser dans l’UKI.
`sb.certificates` contient modules.cer, bundle.sha256 et approved-modules.json.
Les définitions individuelles restent importables avec callPackage ; pour un
driver, utiliser `sb.kernelPackages.callPackage` afin de garder le même noyau.

`sb.boot-tools` fournit glf-secureboot-install et glf-secureboot-sign.
La flake propose aussi base-kernel, kernel, certificates, modules-tree et les
paquets de drivers. Les sorties uki et enrollment restent des artefacts de test.

## NVIDIA

NIX_SB expose `sb.nvidia` (paquet complet) et `sb.drivers.nvidia-open` (modules).
La version et ses hashes sont choisis dans pkgs/drivers/nvidia/version.json.
Le consommateur utilise `hardware.nvidia.package = sb.nvidia;` et
`hardware.nvidia.open = true;` lorsque NVIDIA est activé. Il conserve la gestion
matérielle de PRIME, des services et de l’énergie. Cet exemple ne modifie pas GLF-OS.
Le nixpkgs fourni à callPackage doit autoriser les composants NVIDIA non libres.
