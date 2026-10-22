# Décision actuelle : centre noyau et drivers GLF

NIX_SB gère le choix du noyau depuis nixpkgs, les drivers GLF et la signature.
Ne modifier aucun code GLF-OS ni ancien dépôt de driver. Tests légers uniquement
pour cette passe : aucun build de noyau ni test VM.

## Architecture

- kernel.json sélectionne linuxPackages_6_18 ; flake.lock fixe nixpkgs et donc
  la version exacte (6.18.57 actuellement).
- default.nix reçoit pkgs et expose kernelPackages, kernel, drivers, modulesTree,
  certificates, boot-tools et rocky-shim. La flake exporte aussi legacyPackages.
- Le consommateur réutilise cet ensemble, sans choisir un autre noyau pour les drivers.
  callPackage doit recevoir le même nixpkgs que le dépôt pour la signature CI.
- Fanatec et new-lg4ff sont vos définitions, maintenues directement dans pkgs/drivers.
  Elles récupèrent leurs sources amont avec version/hash fixes. Aucun remplacement
  par les définitions nixpkgs. Provenance détaillée dans docs/drivers.md.
- Catalogue JSON : path local ou package de kernelPackages.
- Sous-flake, second lock, références input/git et synchronisation des anciens
  dépôts retirés. Les modifications de drivers se font ici, en revue.
- Noyau enrichi et certificats partagent l’arbre de modules approuvés. L’image
  enrichie ne sert pas à compiler les drivers, ce qui évite une boucle.
- L’UKI et l’initrd restent spécifiques à chaque poste.

## Signature

Paquet glf-secureboot, commandes glf-secureboot-install et glf-secureboot-sign.
Client et workflows GitHub dans NIX_SB : validation puis signature dans un job
protégé séparé, bootstrap manuel unique refusant d’écraser les secrets existants.
La clé privée reste hors dépôt/store/artefacts. Aucun secret créé ni workflow
distant déclenché. Configuration des protections décrite dans SIGNING-SERVICE.md.

## Conventions et validation

Documentation en français. Consigner les décisions et les résultats réels.
Les résultats de build/VM historiques ne valident pas la refonte actuelle.
La validation de compilation, de chargement des drivers et du parcours de
signature réel reste à réaliser séparément avant déploiement.

Résultats de la centralisation : nix flake check --no-build réussi (noyau
6.18.57 et ses deux drivers), test léger du catalogue réussi, shellcheck,
actionlint et git diff --check réussis. Aucun build ni test VM exécuté.

## Catalogue complet et version NVIDIA

Les sept drivers externes repérés dans GLF-OS/develop sont approuvés :
hid-fanatecff, new-lg4ff, xone, xpadneo, hid-tmff2, v4l2loopback et nvidia-open.
Les pilotes natifs restent couverts par le noyau ; xpad-noone est explicitement
désactivé. v4l2loopback réutilise nixpkgs avec DEPMOD=true pour l’agrégation.
NVIDIA 615.71.09 et ses hashes sont gérés ici dans pkgs/drivers/nvidia/version.json.
Le paquet complet sb.nvidia et les modules sb.drivers.nvidia-open partagent cette
même définition. L’activation reste côté poste, sans modification GLF-OS.
Validation du catalogue complet : évaluation Nix --no-build réussie pour les sept
modules et NVIDIA complet, assertions de cohérence noyau/NVIDIA réussies, test
Python catalogue et git diff --check réussis. Aucune compilation effectuée.

## Ajout xonedo

Huitième entrée : OpenGamingCollective/xonedo, commit
982cbcb019ae4d2bee5ae69385223409ee555c88. Définition locale, installation Kbuild
avec kmodigest, répertoire extra/xonedo pour distinguer les fichiers de xone.
Même noms de modules xone_* : le poste doit choisir l’une des variantes.
Aucun remplacement automatique de xone/xpadneo ni changement GLF-OS.
Validation xonedo : nix flake check --no-build et test léger du catalogue réussis,
git diff --check propre. Aucun build, chargement matériel ou test VM exécuté.

Suite légère complète relancée à la demande de l’utilisateur : ci/check.sh
réussi (code 0), évaluation Nix de toutes les sorties dont huit drivers, noyau
6.18.57 et NVIDIA 615.71.09, shellcheck/actionlint et 9 tests Python réussis.
Le refus « dépôt public » affiché est un test négatif attendu du client simulé.
Aucun appel GitHub réel, aucune clé créée, aucun build ni démarrage VM.

## Validation réelle autorisée et exécutée

L’utilisateur a demandé de passer aux vrais builds/tests. Résultats détaillés
et limites dans docs/VALIDATION.md : noyau et UKI construits, 29 certificats des
8 drivers présents, signatures PE réelles avec clé jetable, démarrages Secure Boot
réussis en VM pour xone puis xonedo, module altéré refusé. Les pilotes de volants,
xpadneo, v4l2loopback et modules Xbox testés se chargent. NVIDIA n’a pas été testé
sur GPU. Ni CI distante ni clé persistante ni installation sur l’hôte.
Correction du script d’export pour remplacer les anciens fichiers en lecture seule.

## Branches par version

À la demande de l’utilisateur, la refonte est publiée sur Rising, nom de la version
GLF-OS ciblée. Une branche par version : chaque push lance validation et build,
les PR gardent les contrôles légers. Les artefacts et release.json identifient
la branche et le commit. La signature exige --ref explicite et branche protégée,
avec la même clé persistante du dépôt. Aucune génération de clé par version.
La protection Rising et les autorisations d’environnement ne sont pas configurées
par les fichiers du dépôt ; elles restent des réglages GitHub.
Validation avant publication Rising : suite ci/check.sh réussie, export des images
avec release.json réussi ; le manifeste identifie Rising et la révision nixpkgs.

## Préparation production

L’utilisateur demande la création de la clé réelle et le parcours de récupération.
Inspection : glf-signing contient encore les deux secrets de test (empreinte du
certificat 50AF89E91B921AAC33E91A6CC48497658B5DC5E32ABB561AF7A15CF226DCC08C).
Créer une clé distincte dans glf-signing-production, jamais remplacer la clé test.
Environnements production et bootstrap préparés avec reviewer Xdavius et branche
Rising autorisée. Un jeton temporaire Environments:write doit être fourni dans
GLF_KEY_ADMIN_TOKEN ; ne pas réutiliser/transférer l’authentification locale.
Le workflow doit être sur la branche par défaut : choix demandé à l’utilisateur.
Aucune clé de production créée à ce stade. Récupération actuelle via client GitHub,
non adaptée à une flotte anonyme sans service intermédiaire ; voir documentation.

## Clé de production créée le 22 octobre 2026

Bootstrap 39764263507 approuvé par l’utilisateur et terminé avec succès.
Clé privée enregistrée dans glf-signing-production, jamais téléchargée.
Certificat public récupéré dans certificates/production, PEM/DER et empreinte
vérifiés : 633FDE4E911D1002BBD58B3945D02BC43F1B840E6F0D5C953B573E77A656BFBF.
Rising est maintenant la branche par défaut et reste protégée.
GLF_KEY_BOOTSTRAP_ENABLED remis à false ; secret temporaire GLF_KEY_ADMIN_TOKEN
retiré du bootstrap. Révoquer aussi le jeton personnel côté compte GitHub.
La signature de production reste désactivée jusqu’à sa validation dédiée ;
aucune signature de poste réel ni modification GLF-OS effectuée.
