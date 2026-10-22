# NIX_SB — noyau et drivers GLF

Une branche correspond à une version GLF-OS : **Rising** pour la version actuelle.
Chaque push déclenche les contrôles et le build des artefacts de cette branche.

Ce dépôt centralise le choix du noyau nixpkgs, les définitions des drivers GLF,
le catalogue de confiance et les outils de signature Secure Boot.

- `kernel.json` : famille du noyau choisie dans nixpkgs (`linuxPackages_6_18`).
- `flake.lock` : révision nixpkgs, qui fixe la version exacte du noyau (actuellement 6.18.57).
- `pkgs/drivers/catalogue.json` : les sept drivers externes GLF-OS et xonedo.
- `pkgs/drivers/nvidia/version.json` : version NVIDIA et hashes, gérés ici.
- `pkgs/drivers/hid-fanatecff` et `new-lg4ff` : vos définitions désormais maintenues ici.
- `pkgs/kernel` : sélection du noyau et production de son image enrichie des certificats.
- `pkgs/boot-tools` et `.github/workflows` : client, installation, signature et bootstrap de clé.

```nix
sb = pkgs.callPackage sourceNixSb {};
# sb.kernelPackages : noyau de base et ensemble de compilation des modules
# sb.kernel : image enrichie pour l’UKI
# sb.drivers, sb.nvidia, sb.modulesTree, sb.certificates, sb.boot-tools, sb.rocky-shim
```

La version exacte approuvée est celle du nixpkgs verrouillé dans ce dépôt.
Un consommateur de `callPackage` doit utiliser cette même révision pour obtenir
les mêmes composants que la CI. La flake expose aussi l’ensemble cohérent dans
`legacyPackages.x86_64-linux`. Voir [docs/usage.md](docs/usage.md).

Les deux drivers GLF sont des définitions locales qui récupèrent leurs sources
amont à version/hash fixes. Il n’y a plus de sous-flake ni de synchronisation avec
les anciens dépôts de packaging. Une modification noyau/driver se fait ici.
Aucun fichier GLF-OS ni ancien dépôt de driver n’est modifié automatiquement.

## Vérifications légères

```sh
nix flake check "path:$PWD" --no-build --no-update-lock-file
python3 -m unittest discover -s tests -p test_catalogue.py
```

Pas de build noyau ni de VM dans ces contrôles. La configuration de test produit
une UKI fictive ; l’UKI réelle conserve l’initrd et les paramètres de chaque poste.

Documentation : [drivers](docs/drivers.md), [architecture](docs/architecture.md),
[signature](docs/SIGNING-SERVICE.md), [CI](docs/CI.md).
