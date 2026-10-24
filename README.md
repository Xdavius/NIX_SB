# NIX_SB — noyau et drivers GLF

Une branche correspond à une version GLF-OS : **Rising** pour la version actuelle.
Deux profils sont définis : current (glf-os-channels) et testing (testing-channels).
Temporairement, seul testing est construit et publié ; current est explicitement
indisponible et non bloquant pour la fusion. Les contrôles testing restent obligatoires.

Ce dépôt centralise le choix du noyau nixpkgs, les définitions des drivers GLF,
le catalogue de confiance et les outils de signature Secure Boot.

- `kernel.json` : famille du noyau choisie dans nixpkgs (`linuxPackages_6_18`).
- `flake.lock` : fichier local/CI temporaire, ignore par Git ; les versions viennent des channels GLF-OS.
- `pkgs/drivers/catalogue.json` : les sept drivers externes GLF-OS et xonedo.
- `pkgs/drivers/nvidia/version.json` : version NVIDIA et hashes, gérés ici.
- `pkgs/drivers/hid-fanatecff` et `new-lg4ff` : vos définitions désormais maintenues ici.
- `pkgs/kernel` : sélection du noyau et production de son image enrichie des certificats.
- `pkgs/boot-tools` et `.github/workflows` : installation sans UKI, publication signée et bootstrap de clé.

```nix
sb = pkgs.callPackage sourceNixSb {};
# sb.kernelPackages : noyau de base et ensemble de compilation des modules
# sb.kernel : image enrichie avant signature
# sb.drivers, sb.nvidia, sb.modulesTree, sb.certificates, sb.boot-tools, sb.rocky-shim
```

GLF-OS conserve les révisions nixpkgs et unstable définies par `channels-glfos`.
La sous-flake `glf-apps` référence ce dépôt avec `flake = false` et expose ses
paquets via `callPackage`, sans consommer ses sorties de flake. La CI suit
le socle de chacun des deux dépôts channels. Current reste incompatible avec
`rebuildImage` ; testing fournit le mécanisme requis. Aucun mélange des profils.
Voir [docs/usage.md](docs/usage.md) et [integration-glfos.md](integration-glfos.md).

Les deux drivers GLF sont des définitions locales qui récupèrent leurs sources
amont à version/hash fixes. Il n’y a plus de sous-flake ni de synchronisation avec
les anciens dépôts de packaging. Une modification noyau/driver se fait ici.
Aucun fichier GLF-OS ni ancien dépôt de driver n’est modifié automatiquement.

## Vérifications légères

```sh
nix flake update --flake "path:$PWD" --refresh
nix flake check "path:$PWD" --no-build --no-update-lock-file
python3 -m unittest discover -s tests -p test_catalogue.py
```

Pas de build noyau ni de VM dans ces contrôles. La CI publie le noyau et le
chargeur signés une fois par commit. Chaque poste conserve un initrd séparé.
Les sorties UKI/enrollment historiques restent des fixtures de test.

Voir [le guide GLF-OS](integration-glfos.md) pour épingler une publication via
`signedReleaseFile` et utiliser `sb.signed.bundle`, `sb.signed.kernel` et
`sb.signed.bootloader`. Aucun jeton de signature sur les postes.

Documentation : [drivers](docs/drivers.md), [architecture](docs/architecture.md),
[signature](docs/SIGNING-SERVICE.md), [CI](docs/CI.md).
