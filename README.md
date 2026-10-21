# GLF-OS — UKI, systemd-boot et Secure Boot

Prototype **NixOS unstable**, x86_64, avec la chaîne :

```text
UEFI → shim signé Rocky → systemd-boot signé GLF → UKI signée GLF
```

Les certificats des modules sélectionnés sont produits par `kmodigest`, agrégés
par NixOS, puis injectés dans le noyau via `kernelPackages.rebuildImage`.
L’UKI utilise la configuration complète de la machine : matériel, initrd,
paramètres et génération système.

## Import dans GLF-OS

Le dépôt expose `nixosModules.default`, `overlays.default` et le paquet
`glf-boot-tools`. L’import est sans effet tant que `glf.boot.enable` reste faux.
Le patch [integration/glf-os.patch](integration/glf-os.patch) prépare le passage
par la flake `modules/glf-apps` de GLF-OS. Il n’a pas été appliqué au checkout
externe ni à `/etc/nixos`.

Une fois le module importé, `glf.boot.enable = true` raccorde l’installation à
`nixos-rebuild boot/switch`, donc au parcours existant de `glf-update`.
Voir [INTEGRATION-GLF.md](docs/INTEGRATION-GLF.md) pour les options et limites.

## Signature distante

La clé persistante **de test** reste uniquement dans GitHub Secrets. Le poste
soumet ses images à `sign-request.yml`, attend l’approbation de `glf-signing`,
vérifie les signatures et le contenu retourné, puis installe les fichiers.
Le certificat public est [GLF-TEST.cer](certificates/GLF-TEST.cer).

Ce parcours demande un accès GitHub sur le poste et un workflow fusionné sur
`main`. Les images d’une machine sont potentiellement sensibles : les artefacts
d’un dépôt public nécessitent une autorisation explicite dans la configuration.
Aucune clé de production n’a été créée. Voir [SIGNING-SERVICE.md](docs/SIGNING-SERVICE.md).

## Sorties de la flake

| Sortie | Usage |
| --- | --- |
| `.#kernel`, `.#uki`, `.#certificates` | Artefacts de la machine fictive de CI. |
| `.#systemd-boot` | systemd-boot non signé, destiné à l’étape de signature. |
| `.#rocky-shim` | Shim Rocky et MokManager signés, conservés intacts. |
| `.#enrollment` | Dossier USB d’enrôlement du certificat de test. |
| `.#glf-boot-tools` | Client GitHub et installateur des générations. |

Les paquets et modules d’un vrai poste se déclarent dans sa configuration NixOS,
via `environment.systemPackages` et `boot.extraModulePackages`. Les sources
peuvent être locales ou venir d’inputs Git verrouillés. Construire les modules
externes avec `config.boot.kernelPackages` pour respecter le noyau choisi.

## Vérification

```sh
nix develop .#ci --command bash ci/check.sh
nix build .#kernel .#uki .#glf-boot-tools
```

[CI.md](docs/CI.md) décrit les vérifications et la publication Attic simulée.
[ENROLLMENT.md](docs/ENROLLMENT.md) décrit MokManager. Le support d’enrôlement
reste distinct du démarrage normal par systemd-boot.

Les fonctionnalités sont destinées au prototype. La validation sur le matériel
GLF-OS et le parcours distant après fusion du workflow restent nécessaires avant
utilisation sur un poste réel.
