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

1. Embarque `module.sig_enforce=1` et `lockdown=integrity` dans la ligne de
   commande protégée par la signature de l’UKI. Le noyau conserve la configuration
   native nixpkgs et ses signatures kmodigest.
2. Utilise les signatures déterministes et les certificats produits par
   `kmodigest` dans nixpkgs.
3. Récupère `modules.cer` dans `system.modulesTree`, qui agrège les modules du
   noyau et `boot.extraModulePackages`.
4. Appelle `kernelPackages.rebuildImage { modulesTree = …; }` pour injecter ces
   certificats dans le noyau final avec `insert-sys-cert`.
5. Construit une UKI dont la section Linux utilise explicitement ce noyau enrichi.

Les sorties système sont `.#kernel`, `.#certificates` et `.#uki`.
Les sorties `.#rocky-shim` et `.#enrollment` fournissent séparément le shim Rocky
signé et le dossier d’enrôlement. Le job `validate` construit et publie ce dernier
comme artefact `enrollment-x64-<commit>`, sans clé privée ni build complet du noyau.
Voir [ENROLLMENT.md](ENROLLMENT.md). Le build ne reçoit
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
NixOS. Le module fournit l’installation sur l’ESP du shim, de MokManager, de systemd-boot et de l’UKI ; son activation sur les postes reste à réaliser.

## Mode actif : clé de test persistante

Une clé RSA 3072 bits dédiée aux tests a été créée le 21 octobre 2026. Son
certificat porte le nom **GLF-OS TEST ONLY Secure Boot**, avec une validité d’un
an. Elle est conservée dans `GLF_SIGNING_KEY_PEM`, au sein de l’environnement
GitHub protégé `glf-signing`. Sa copie privée locale temporaire a été supprimée.
La même clé est réutilisée entre les builds, sans régénération automatique.

Les fichiers [GLF-TEST.cer](../certificates/GLF-TEST.cer) (DER) et
[GLF-TEST.pem](../certificates/GLF-TEST.pem) sont publics. L’empreinte SHA-256
attendue est enregistrée dans la variable d’environnement GitHub `GLF_CERT_SHA256`.
La signature et la vérification d’un stub EFI avec cette clé ont réussi localement.

`GLF_SIGNING_ENABLED=true` autorise désormais le parcours PEM **pour les tests**.
Le workflow doit toujours être déclenché manuellement sur `main` avec `sign=true`,
puis approuvé dans l’environnement `glf-signing`. La création de la clé n’a pas
lancé de compilation complète, de déploiement ou d’enrôlement MOK.

Le certificat à enrôler sur la machine de test est `GLF-TEST.cer`. Le script
existant conserve le nom technique `GLF.cer` dans les artefacts de signature :
il s’agit du même certificat de test, identifiable par son sujet et son empreinte.
Ne pas le présenter comme un certificat de production. La publication Attic reste
simulée. Si le secret GitHub est perdu, cette clé n’a pas de sauvegarde privée
locale : il faudra créer une autre clé de test et enrôler son nouveau certificat.

L’administrateur du dépôt peut techniquement extraire un secret en modifiant un
workflow. Cette limitation est acceptée uniquement pour la clé de test. La future
clé GLF de production reste distincte et devra respecter l’exigence de
non-exportabilité, si celle-ci est maintenue.

L’environnement `glf-signing` est restreint à `main` et demande une validation de
`Xdavius`. Cette validation peut être donnée par le déclencheur lui-même. Les
protections de branche imposent séparément une revue de PR.

### Configuration du parcours PEM de test

La configuration suivante est déjà appliquée ; ne pas remplacer les secrets
existants ni créer une nouvelle clé à chaque build.

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

La même clé de test est réutilisée : la CI de publication ne génère et ne
remplace jamais cette clé.
Une rotation éventuelle doit être une opération explicite accompagnée d’un
nouvel enrôlement ; elle n’est pas automatisée ici.

Le job de signature utilise un runner GitHub hébergé distinct du build. Les outils
sont préparés avant l’injection des secrets. Le script écrit la clé dans un
répertoire temporaire privé, vérifie l’empreinte et la correspondance clé/certificat,
signe le noyau, systemd-boot et l’UKI avec `sbsign`, puis vérifie avec `sbverify`. La clé est
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

Vérifié localement le 21 octobre 2026 : évaluation Nix (dont le contrat d’import
et la conservation des paramètres machine), Actionlint, ShellCheck, signature,
installation de deux générations et retour à la précédente sur ESP simulée,
refus des réponses altérées et tests du client GitHub avec API simulée.
Le noyau enrichi 6.18.57, l’UKI et les outils ont été construits réellement.
Les paramètres signés imposent la vérification des modules et lockdown integrity.

Le test QEMU/OVMF vérifie le démarrage via shim Rocky et systemd-boot avec une
clé jetable présente uniquement dans MOK, Secure Boot actif, lockdown integrity,
le chargement d’efivarfs signé par kmodigest et le rejet du même module altéré.
Il ne teste pas l’interface interactive d’enrôlement MokManager, les deux modules
maison, le firmware physique ni la signature distante réelle après fusion.
La clé jetable de VM est indépendante de la clé GLF conservée dans GitHub.

Références : [kmodigest](https://github.com/emilazy/boot-security-tools/tree/main/kmodigest),
[rebuild-image.nix à la révision verrouillée](https://github.com/NixOS/nixpkgs/blob/02c087f3fe673c9e317f206a627cb6b910336dbe/pkgs/os-specific/linux/kernel/rebuild-image.nix),
[environnements GitHub](https://docs.github.com/en/actions/reference/workflows-and-actions/deployments-and-environments),
[CLI Attic](https://docs.attic.rs/reference/attic-cli.html).

## Signature des machines et installation

`sign-request.yml` fournit le parcours distant décrit dans
[SIGNING-SERVICE.md](SIGNING-SERVICE.md). La CI de build signe désormais aussi
`systemd-bootx64.efi`. Le module opt-in fournit l’installateur exécuté par
`nixos-rebuild boot/switch` ; le workflow doit être fusionné sur `main` avant usage.
Les tests d’installation assemblent de vraies UKI et vérifient les signatures sur
une ESP simulée, y compris le refus d’une réponse signée au contenu différent.

Test UEFI facultatif (QEMU/OVMF, sans accès au firmware hôte) :

```sh
nix build .#kernel --out-link result-kernel
nix develop .#vm --command python3 tests/test_uefi.py result-kernel/bzImage
```
