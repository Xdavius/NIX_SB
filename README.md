# GLF-OS — service de signature Secure Boot

L’implémentation système est désormais intégrée directement au dépôt GLF-OS,
dans `secureboot/`, sur la branche `feature/secureboot-uki`. Le module est importé
par GLF-OS ; son activation passe par `glf-securebootUKI.enable` dans customConfig.

Ce dépôt conserve le service GitHub et la clé privée de test. Le build signé
utilise uniquement la révision GLF-OS verrouillée dans
[ci/approved-source.json](ci/approved-source.json).

Voir [MIGRATION-GLF.md](docs/MIGRATION-GLF.md) pour l’architecture, les tests et
les conditions de déploiement. Les fichiers du prototype ci-dessous restent un
banc de tests historique et ne sont plus l’intégration à installer dans GLF-OS.

---

# GLF-OS — UKI, systemd-boot et Secure Boot

Prototype **NixOS unstable**, x86_64, avec la chaîne :

```text
UEFI → shim signé Rocky → systemd-boot signé GLF → UKI signée GLF
```

Les certificats des modules natifs et du catalogue GLF approuvé sont produits par `kmodigest`, agrégés
par NixOS, puis injectés dans le noyau via `kernelPackages.rebuildImage`.
L’UKI utilise la configuration complète de la machine : matériel, initrd,
paramètres et génération système.

## Import dans GLF-OS

Le dépôt expose `nixosModules.default`, `overlays.default` et le paquet
`glf-boot-tools`. L’import est sans effet tant que `glf-securebootUKI.enable` reste faux.
Le patch [integration/glf-os.patch](integration/glf-os.patch) prépare le passage
par la flake `modules/glf-apps` de GLF-OS. Il n’a pas été appliqué au checkout
externe ni à `/etc/nixos`.

Une fois le module importé, `glf-securebootUKI.enable = true` raccorde l’installation à
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

Les modules externes approuvés sont définis dans
[pkgs/repo/default.nix](pkgs/repo/default.nix) : `hid-fanatek` et `new-lg4ff`.
Le bundle de confiance est indépendant des ajouts de la configuration du poste.
Un nouveau driver, local ou Git, exige une modification revue de ce catalogue ;
voir [la procédure](pkgs/repo/README.md). Les applications ordinaires restent
librement sélectionnables via `environment.systemPackages`.

Le signataire compare le noyau et systemd-boot aux builds du dépôt protégé et
reconstitue l’UKI avec le stub approuvé. Modifier le catalogue localement ne
suffit donc pas à obtenir une signature GitHub. Le noyau et les paquets du poste
doivent correspondre à la révision approuvée par le service.

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
