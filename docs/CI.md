# CI du prototype

La CI utilise GitHub Actions pour une **machine fictive de test**. Ses artefacts
ne sont pas l’UKI d’un poste GLF-OS. L’intégration à la configuration utilisée par
`glf-update` est décrite dans [INTEGRATION-GLF.md](INTEGRATION-GLF.md). Les pull requests et les pushes vers `main`,
`master` ou `develop` exécutent les validations. Le build complet, coûteux en
temps et en disque, se lance par **Run workflow**. L’architecture initiale est
`x86_64-linux` ; la racine de test est une partition ext4 portant le label
`GLF_ROOT`, à adapter dans `tests/fixtures/machine.nix`.

## Build sans secret

`flake.lock` verrouille `nixos-unstable`. Le module `nix/secure-boot.nix` :

1. Active la vérification obligatoire des signatures de modules et le lockdown
   en mode integrity.
2. Utilise les signatures déterministes et les certificats produits par
   `kmodigest` dans nixpkgs.
3. Récupère `modules.cer` dans `system.modulesTree`, qui agrège les modules du
   noyau et `boot.extraModulePackages`.
4. Appelle `kernelPackages.rebuildImage { modulesTree = …; }` pour injecter ces
   certificats dans le noyau final avec `insert-sys-cert`.
5. Construit une UKI dont la section Linux utilise explicitement ce noyau enrichi.

Les sorties sont `.#kernel`, `.#certificates` et `.#uki`. Le build ne reçoit
aucune clé GLF. Les modules `hid-fanatek` et `new-lg4ff` ne sont pas encore
raccordés : le build initial utilise les modules du noyau NixOS. Leur ajout se
fait dans la configuration de la machine avec `boot.extraModulePackages` (dans
`tests/fixtures/machine.nix` seulement pour les tests), en utilisant le même
`config.boot.kernelPackages`. Les définitions des paquets externes doivent
préserver le mécanisme `kmodigest` et leurs `.ko.cer` ; leur chargement devra être
testé. Une source Git peut être ajoutée comme input verrouillé, avec
`flake = false` si elle ne fournit pas de flake, puis construite par une
définition Nix locale. Les applications vont dans `environment.systemPackages`.

Le système complet référencé par l’UKI doit exister dans le store de la machine
cible. Télécharger uniquement l’UKI et le noyau ne constitue pas une installation
NixOS. Le déploiement du système, du shim Rocky et de MokManager reste à réaliser.

## Activer la signature GLF

Configurer dans les paramètres GitHub, avant le premier lancement signé :

1. Protéger la branche de publication et imposer une revue des modifications de
   la CI et des scripts de signature.
2. Créer l’environnement **`glf-signing`**, restreint à cette branche protégée,
   avec validation par un responsable lorsque le forfait GitHub le permet.
3. Ajouter uniquement dans cet environnement les secrets `GLF_SIGNING_KEY_PEM`
   (clé privée GLF PEM, non chiffrée au moment de son utilisation) et
   `GLF_SIGNING_CERT_PEM` (certificat public correspondant, PEM).
4. Définir dans l’environnement la variable `GLF_CERT_SHA256` : empreinte SHA-256
   du certificat, hexadécimale, avec ou sans deux-points, sans préfixe.
5. Activer la variable de dépôt `GLF_SIGNING_ENABLED=true`, puis lancer le
   workflow depuis la branche protégée en cochant `sign`.

La même clé GLF existante est réutilisée : la CI de publication ne génère et ne
remplace jamais cette clé. Sa sauvegarde reste sous la responsabilité de GLF.
Une rotation éventuelle doit être une opération explicite accompagnée d’un
nouvel enrôlement ; elle n’est pas automatisée ici.

Le job de signature utilise un runner GitHub hébergé distinct du build. Les outils
sont préparés avant l’injection des secrets. Le script écrit la clé dans un
répertoire temporaire privé, vérifie l’empreinte et la correspondance clé/certificat,
signe le noyau et l’UKI avec `sbsign`, puis vérifie avec `sbverify`. La clé est
retirée de l’environnement des sous-processus après sa copie et le répertoire
temporaire est supprimé à la sortie. Seuls les fichiers publics sont archivés.

Ce choix confie une copie chiffrée au stockage de secrets GitHub et expose la clé
en clair au processus de signature pendant le job. Il ne fournit pas la garantie
d’une clé non exportable : un workflow ou runner compromis pourrait la lire.
Pour cette garantie, remplacer ultérieurement cette étape par un service de
signature ou HSM contrôlé par GLF. Ne pas utiliser un runner partagé persistant
pour stocker la clé GLF.

## Attic simulé

Après une signature réussie, `ci/attic-mock.sh` vérifie les empreintes et écrit
`dist/attic-mock.json` avec `mode: mock` et `uploaded: false`. Aucun client Attic
n’est appelé, aucun serveur ni token n’est requis. Les artefacts sont conservés
sur GitHub pendant sept jours.

Le manifeste distingue les chemins du store construits sans signature GLF et
les fichiers EFI signés. Pour une publication réelle, il faudra importer les
artefacts signés publics dans le store, conserver les références à la closure
NixOS, puis publier ces chemins avec `attic push`. La clé de signature du cache
Nix/Attic est distincte de la clé Secure Boot GLF.

## Vérifications et limites

```sh
nix develop .#ci --command bash ci/check.sh
bash ci/build.sh
```

Avant le premier commit, utiliser une référence `path:` pour que Nix inclue les
nouveaux fichiers non suivis :

```sh
nix develop path:.#ci --command env GLF_FLAKE_REF=path:. bash ci/check.sh
```

Les validations comprennent l’évaluation Nix, la vérification du noyau référencé
par l’UKI, ShellCheck et un test de signature sur un stub EFI avec une clé
**jetable de test**. Ce test vérifie aussi le refus des secrets absents, d’une
mauvaise empreinte, d’une clé incompatible et d’un artefact modifié. Cette clé
de test ne peut pas servir de repli à la signature GLF.

Ces contrôles ne prouvent pas le démarrage Secure Boot. Restent à valider la
compilation complète, les modules maison, l’injection effective des certificats
dans le noyau exécuté, la compatibilité shim/SBAT, l’enrôlement GLF et les refus
de chargement sur une cible UEFI.

Vérifié localement le 21 octobre 2026 : évaluation de toutes les sorties Nix,
Actionlint, ShellCheck, tests de signature et génération effective de la
configuration du noyau 6.18.57. Cette configuration active `MODULE_SIG_FORCE`,
`MODULE_SIG_ALL`, `LOCK_DOWN_KERNEL_FORCE_INTEGRITY` et réserve 3 120 000 octets
pour `SYSTEM_EXTRA_CERTIFICATE`. La compilation complète n’a pas été exécutée.

Références : [kmodigest](https://github.com/emilazy/boot-security-tools/tree/main/kmodigest),
[rebuild-image.nix à la révision verrouillée](https://github.com/NixOS/nixpkgs/blob/02c087f3fe673c9e317f206a627cb6b910336dbe/pkgs/os-specific/linux/kernel/rebuild-image.nix),
[environnements GitHub](https://docs.github.com/en/actions/reference/workflows-and-actions/deployments-and-environments),
[CLI Attic](https://docs.attic.rs/reference/attic-cli.html).
