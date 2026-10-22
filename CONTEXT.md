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

Test réel de signature autorisé avec publication des images fictives : run
39765656321 arrêté avant signature, release draft invisible au GITHUB_TOKEN
contents:read. Correctif : contents:write seulement sur le job de validation.
La signature a été redésactivée après le lancement du test. Aucune clé utilisée
par le run échoué. Demande conservée : glf-sign-fdb06e4dec284dada8c7187fa57a5ca9.

L’utilisateur a explicitement autorisé contents:write pour le seul job validate
et la suppression de l’approbation manuelle du job sign. Conserver la restriction
Rising, la protection de branche et la vérification des images. Le bootstrap
reste désactivé et sa revue manuelle distincte est conservée.

## Cible sans UKI — décision et première validation

L’utilisateur abandonne les UKI et les demandes de signature par poste :
NIX_SB doit publier noyau et chargeur signés une fois par version, accompagnés
du shim Rocky intact, de MokManager et du certificat public GLF. GLF-OS construit
son initrd localement, sans jeton de signature. Initrd et paramètres ne sont pas
authentifiés par cette chaîne. Aucun changement du dépôt GLF-OS autorisé.

La première étape est validée : tests/test_uefi.py, GLF_VM_BOOT_MODE=split,
GLF_VM_VARIANT=xonedo, démarre via shim Rocky et systemd-boot avec noyau signé
et initrd séparé. Secure Boot=1, lockdown integrity, pilotes chargés, module
altéré rejeté. GLF_VM_CORRUPT_KERNEL=1 confirme aussi le refus d’un noyau altéré
(Security Violation, aucun démarrage Linux). Clé jetable et firmware de VM
uniquement. Voir docs/VALIDATION.md.

La CI, les paquets de publication signés et l’installateur restent à migrer.
Le guide integration-glfos.md porte un avertissement : son ancien parcours
UKI ne doit plus être intégré. Systemd-boot peut être conservé pour la suite.

Pour mémoire, avant ce changement de cible, la signature automatique de production
avait réussi dans le run 39766464511, avec récupération et vérification des trois
images fictives. Ne pas confondre ce succès historique avec la future publication
sans UKI, qui n’est pas encore implémentée.


## Refonte centralisée autorisée et implémentée localement

Après refus de l’auto-review, l’utilisateur a explicitement confirmé le
remplacement complet du service par poste, suppressions incluses. Le workflow
sign-request et le client github_sign sont retirés. Le workflow uki.yml conserve
son chemin mais construit sans UKI, signe via glf-signing-production puis publie
une release par branche/commit (draft jusqu’à la fin des uploads, pas de clobber).
ci/package-release.sh produit l’archive et release.json (URL/hash Nix/commit/branche).

API : argument racine signedReleaseFile facultatif, sb.signed=null sans lui ;
sinon bundle/kernel/bootloader vérifiés dans pkgs/signed. Paquet public
secureboot-certificate ajouté. Outils version 0.3.0, installateur sans réseau,
métadonnées version 2 (signedBundle/kernel/initrd/kernelParams). Entrées type 1,
conservation des générations, signatures et correspondance du noyau vérifiées.
Guide integration-glfos.md réécrit et docs actives mises à jour.

Tests réels locaux avec clé jetable : installation/rollback, refus signature
altérée et mauvais noyau, contrôles paramètres, signature/archive, hash NAR,
import réel fetchzip et construction du bundle Nix. Le test Nix utilise une copie
isolée du paquet avec certificat jetable, jamais la clé/certificat de production.
Reste : publication réelle après commit/PR/fusion, intégration GLF-OS et matériel.
Aucune publication distante ni modification de GLF-OS pendant cette refonte.


## Contrat GLF-OS précisé par l’utilisateur

channels-glfos est l’autorité pour les pins nixpkgs et nixpkgs-unstable par version.
GLF-OS ne doit PAS consommer la flake NIX_SB. La sous-flake modules/glf-apps
référence ce dépôt comme source flake=false et fournit les paquets par callPackage
via son overlay. Les exemples du guide ont été corrigés ; API racine déjà compatible.
Lecture seule des copies locales GLF-CHANNELS et glf-os : structure confirmée,
URL Git réelle utilisée localement :
https://framagit.org/gaming-linux-fr/glf-os/channels-glfos/glf-os-channels.git
L’URL groupe fournie n’est pas accessible via web ; pas de vérification distante.
Aucun fichier GLF-OS/channels modifié. La flake interne NIX_SB conserve pour l’instant
son ancien nixpkgs unstable : alignement CI sur le socle channels encore à réaliser,
sans prétendre que les tests précédents démontrent sa compatibilité avec GLF-OS.


## Responsabilité des mises à jour GLF-OS

Correction explicite de l’utilisateur : glf-update est responsable des mises
à jour, pas glf-boot. Le guide raccorde donc glf-secureboot-install au parcours
de glf-update après construction de la génération cible. Aucun code GLF-OS modifié.


## Alignement CI demandé, réalisé avec blocage de compatibilité découvert

Le dépôt Git channels réel est accessible (l’URL groupe ne l’était pas).
main distant = dc9d3bd4bf372fa8b0894bd565013aa0225eced0, identique au lock GLF-OS.
La flake NIX_SB et son lock suivent désormais glf-channels/nixpkgs et unstable.
Socle nixpkgs choisi conformément au module boot.nix GLF-OS (lecture seule).
ci/channels.py vérifie follows/pins et permet la comparaison avec un lock GLF-OS.
ci/build.sh trace channels et les deux pins dans le manifeste de publication.

ATTENTION : nix flake check échoue désormais sur rebuildImage absent.
Les deux pins channels (nixpkgs 26f4107e47e3ad0ffd0db220469ba83b6f6d96e8,
unstable 55bfb4d7437bd4e09ab7cba58a43bd68eb310044) fournissent 6.18.56,
aggregateModules présent mais rebuildImage absent. Ancien pin 02c087f fourni
6.18.57 et rebuildImage. Aucun changement channels ni GLF-OS effectué.
Choix nécessaire : mise à jour channels vers un pin compatible ou rétroportage
réel du mécanisme (pas simple alias). Ne pas prétendre les tests antérieurs
valident les pins alignés. Alignement lock vérifié, évaluation globale bloquée.


## Deux canaux exigés : current et testing

Correction utilisateur : glf-os-channels pour la version actuelle, testing-channels
pour testing. Noms/URLs vérifiés via code GLF-OS en lecture seule et git ls-remote.
La flake verrouille les deux dépôts ; testing-channels main = dbb24ffcb03dfd95d9474d76c953da0f0ec729e4.
Son nixpkgs résout vers 02c087f (rebuildImage présent), unstable vers 9fbb54b.
Les inputs testing peuvent suivre une branche : le lock fixe les commits résolus.
Ne pas exiger que original.rev existe, ni confondre testing avec unstable current.

Sorties internes préfixées testing- (packages/checks/devShells) en plus de current.
CI uki.yml orchestre matrice current/testing fail-fast=false via channel.yml,
chaînes indépendantes et statut global validate exigeant les deux réussites.
Artefacts, tags et descripteurs incluent le profil. GLF_CHANNEL choisit les sorties
pour ci/build.sh et ci/check.sh. Le paquet signé vérifie aussi le profil du manifeste.
Current reste bloqué par rebuildImage absent ; testing s’évalue correctement.
Aucun GLF-OS ni channel modifié, aucune publication distante lancée.
