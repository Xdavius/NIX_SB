# Contexte du prototype GLF-OS

## Objectif

Prototyper, avec Nix, un noyau distribué sous forme d’UKI (Unified Kernel
Image) signé pour GLF-OS, utilisable avec UEFI Secure Boot et capable de charger
les modules noyau maison signés avec les certificats correspondants.

Le prototype doit prendre en compte les certificats publics `.cer` de ces
modules dans la chaîne de confiance du noyau. Le mécanisme retenu est
`kernelPackages.rebuildImage` avec le `system.modulesTree` agrégé ; son résultat
reste à valider au démarrage.

## Choix actés pour le prototype

- Utiliser exclusivement **NixOS unstable** comme base du prototype, avec une
  révision de `nixpkgs` verrouillée pour la reproductibilité. La compatibilité
  avec les branches stables n’entre pas dans le périmètre de ce prototype.
- Les `.cer` sont générés par **`kmodigest` dans NixOS**. Le code de la révision
  nixpkgs verrouillée confirme leur agrégation dans
  `system.modulesTree/lib/modules/<version>/modules.cer`. `rebuildImage` les
  injecte via `insert-sys-cert` avant la construction de l’UKI. Les signatures
  de modules kmodigest ne nécessitent pas la clé privée GLF.
- GLF-OS reste la cible d’intégration ; le choix d’unstable concerne ici le prototype.
- Réutiliser le **shim déjà signé distribué par Rocky Linux**, accompagné de son
  **MokManager**, et enrôler le certificat public de la clé **GLF** via MOK.
  L’objectif est de signer l’UKI avec la clé GLF sans construire un shim GLF
  nécessitant sa propre signature Microsoft. Les binaires Rocky seront conservés
  intacts ; leur version, provenance et empreinte devront être verrouillées.

## État du prototype

- Flake NixOS unstable verrouillée, cible initiale x86_64 et configuration extensible.
- Sorties Nix pour le noyau enrichi des certificats, leur bundle et l’UKI non signée.
- CI GitHub Actions : validations, build manuel, signature GLF et publication Attic simulée.
- Certificat public de test disponible ; clé privée de test conservée dans GitHub Secrets.
- Modules maison non encore raccordés ; le build utilise les modules NixOS sélectionnés.
- Shim signé Rocky 16.1-2.el10 et MokManager empaquetés sans modification ;
  dossier d’enrôlement de test disponible via `.#enrollment`.
- Aucun démarrage Secure Boot validé ; le déploiement sur les postes reste à réaliser.

## Configuration machine et glf-update

L’UKI de production doit être construite depuis la configuration exacte du poste
qui lance `glf-update`. Le programme installé utilise `/etc/nixos#GLF-OS`.
Le module `nix/secure-boot.nix` doit être importé dans cette configuration ;
`tests/fixtures/machine.nix` sert uniquement aux tests de CI et ne remplace pas
les définitions matérielles ou système du poste.

Les sorties actuelles de la flake et du workflow restent des artefacts de test.
L’assemblage local d’une UKI propre au poste implique un parcours de signature
contrôlé par GLF, ou une construction centrale par configuration machine. La clé
privée GLF ne doit pas être distribuée aux postes. Ce raccordement à `glf-update`
reste à implémenter ; voir [INTEGRATION-GLF.md](docs/INTEGRATION-GLF.md).

## Clé de test et future clé de production

Une clé RSA 3072 bits persistante dédiée aux tests a été créée et enregistrée dans
l’environnement GitHub `glf-signing`. Son certificat public est
`certificates/GLF-TEST.cer`, avec le sujet `GLF-OS TEST ONLY Secure Boot`.
`GLF_SIGNING_ENABLED=true` active le parcours PEM uniquement pour cette clé de
test. La copie privée temporaire locale a été supprimée. La signature d’un stub
EFI a été vérifiée, sans lancer le build complet ni enrôler le certificat.

La limitation de GitHub Secrets (extraction techniquement possible par un
administrateur) est acceptée pour les tests. La clé GLF de production n’existe
pas encore ; son exigence de non-exportabilité reste un sujet distinct.

## CI, publication et clé GLF

La CI doit construire le noyau contenant les `.cer` et l’UKI, puis les signer avec
la même clé privée GLF persistante. Le build Nix s’exécute sans cette clé. La
signature se fait dans un job séparé, sur branche protégée et via l’environnement
GitHub `glf-signing`, à configurer par les responsables GLF.

Sans infrastructure de signature dédiée, la première implémentation utilise des
secrets d’environnement GitHub. La clé ne doit apparaître ni dans le dépôt, ni
dans le store Nix, ni dans les logs, caches ou artefacts. Ce mécanisme ne rend pas
la clé non exportable : une évolution vers HSM/service de signature est nécessaire
pour cette garantie. La CI ne régénère jamais la clé GLF.

La publication Attic est strictement simulée pour cette étape. Elle produit un
manifeste sans transfert réseau. Les artefacts EFI signés restent distincts des
sorties Nix non signées ; leur import dans le store est à prévoir pour Attic réel.
Voir [docs/CI.md](docs/CI.md) pour les paramètres et les limites de sécurité.

## Dépôt principal GLF-OS

Le projet principal est
[glf-os](https://framagit.org/gaming-linux-fr/glf-os/glf-os).
Si le prototype a besoin de consulter ou de réutiliser sa configuration, utiliser
la branche **`develop`**. Cette référence n’impose pas d’ajouter GLF-OS comme
dépendance tant que ce n’est pas nécessaire.

En cas d’intégration au build, verrouiller un commit issu de `develop` pour
préserver la reproductibilité. Le choix de NixOS unstable pour le prototype reste
inchangé. Le dépôt `app-glf-os` ci-dessous constitue une référence distincte pour
les modules ; aucune branche n’a encore été imposée pour celui-ci.

## Modules de référence

Le dépôt [app-glf-os](https://framagit.org/gaming-linux-fr/glf-os/app-glf-os)
est la source indiquée pour les deux premiers modules à intégrer :

- `hid-fanatek` (nom communiqué, orthographe et attribut Nix à vérifier dans la source) ;
- `new-lg4ff`.

Les chemins des définitions, révisions et dépendances restent à relever dans ce
dépôt. Les sorties `.cer` générées par `kmodigest` pour ces modules restent à
identifier dans le build NixOS. Ces deux modules serviront de premiers
cas de validation, sans limiter le prototype à leur prise en charge.

## Exigence d’extension aux paquets

Le prototype doit permettre d’ajouter des paquets depuis deux types de sources :

- **Locales** : définitions Nix et/ou sources conservées dans ce projet.
- **Git externes** : dépôt référencé par son URL, avec une révision verrouillée
  pour rendre les builds reproductibles.

L’ajout doit passer par une configuration déclarative extensible, sans modifier
le mécanisme central d’assemblage et de signature de l’UKI pour chaque paquet.
Le point d’extension est la configuration NixOS du poste : `boot.extraModulePackages`
pour les modules et `environment.systemPackages` pour les autres paquets. Les
sources externes se déclarent comme inputs verrouillés dans `flake.nix` ; les
définitions de build peuvent être locales ou fournies par ces inputs.

Une URL Git désigne une source ; elle ne suffit pas à définir la compilation.
Pour les dépôts qui fournissent déjà un paquet Nix, prévoir la sélection de son
attribut ou de sa définition. Pour les autres, prévoir une définition Nix locale
qui construit les sources externes. Le support ne doit donc pas imposer que tous
les dépôts externes fournissent une flake.

Distinguer deux usages dans cette configuration :

- **Modules noyau** : compilation pour le noyau cible, signature, déclaration des
  certificats de confiance nécessaires et installation ; inclusion dans l’initrd
  uniquement si le démarrage le nécessite.
- **Paquets applicatifs ou utilitaires** : installation dans le système cible,
  avec inclusion éventuelle dans l’initrd selon le besoin. Ils ne suivent pas le
  mécanisme de signature des modules noyau et ne sont pas tous embarqués dans l’UKI.

Les références aux certificats publics doivent être séparées des références aux
clés privées. L’ajout d’un dépôt Git ne suffit pas à accorder la confiance à ses
modules : seuls les paquets explicitement sélectionnés dans la configuration
alimentent `system.modulesTree` et le bundle de certificats injecté.

## Distinction des chaînes de confiance

- La signature de l’UKI doit être reconnue par la chaîne de démarrage Secure Boot
  via le shim Rocky et le certificat GLF enrôlé dans MOK.
- Les signatures des modules maison doivent être reconnues par le noyau exécuté.
- Signer l’UKI ne suffit pas à rendre les certificats des modules fiables pour le
  noyau. Copier des `.cer` dans l’image ne suffit pas non plus : leur intégration
  dans un trousseau de confiance adapté doit être explicitement mise en œuvre.

## Démarrage via le shim Rocky et enrôlement GLF

Le parcours cible est : firmware UEFI avec Secure Boot actif → shim signé Rocky
Linux → UKI signée GLF, avec un éventuel chargeur intermédiaire si l’intégration
le nécessite. Le chargement direct de l’UKI reste à tester avec la version exacte
du shim retenue ; il ne constitue pas encore un résultat acquis.

L’enrôlement concerne le **certificat public** GLF dans la liste MOK gérée par
shim, et non la clé privée ni un remplacement des clés du firmware. Prévoir une
demande d’import via `mokutil`, puis sa confirmation au redémarrage dans le
MokManager correspondant au shim Rocky.

La machine de test doit faire confiance à l’autorité qui a signé ce shim et ne
pas en révoquer le binaire. Vérifier la compatibilité avec les politiques de
révocation DBX/SBAT et les exigences du shim retenu pour les images suivantes.

L’enrôlement GLF pour le démarrage ne résout pas à lui seul la confiance dans les
`.cer` générés par `kmodigest` pour les modules. Leur intégration au noyau conserve
son propre parcours de validation.

Référence de fonctionnement : [documentation amont de shim](https://github.com/rhboot/shim/blob/main/README.md).
Les capacités de la version livrée par Rocky devront être vérifiées séparément.

## Points à préciser avant l’implémentation

- Commit de GLF-OS sur `develop` si nécessaire, version du noyau et architecture cible.
- Révision de NixOS unstable à verrouiller et stratégie de mise à jour des dépendances.
- Composition de l’UKI : noyau, initrd, ligne de commande et métadonnées.
- Compatibilité DBX/SBAT et firmware du shim Rocky 16.1-2.el10 x86_64 retenu ;
  paquet officiel verrouillé par empreinte dans `nix/rocky-shim.nix`.
- Chemins EFI et chargement de l’UKI via ce shim, directement ou avec un chargeur
  intermédiaire ; procédure d’enrôlement MOK du certificat GLF.
- Préservation des sorties DER `.ko.cer` de `kmodigest` par les paquets maison
  et validation de leur présence dans le bundle injecté.
- Définitions de `hid-fanatek` et `new-lg4ff`, méthode de compilation et étape de signature.
- Interface d’ajout des paquets locaux et Git, sélection des définitions Nix et
  verrouillage des révisions externes.
- Configuration effective de l’environnement GitHub protégé, sauvegarde GLF de
  la clé persistante et évolution éventuelle vers un service de signature/HSM.
- Environnement de validation : machine virtuelle UEFI et/ou machine de test.

## Plan de travail envisagé

1. Définir une configuration NixOS unstable reproductible pour le prototype GLF-OS.
   Prévoir l’interface des paquets locaux et Git, avec les deux modules de référence.
2. Produire un noyau et un initrd, puis assembler une UKI.
3. Récupérer les `.cer` générés par `kmodigest` et intégrer la confiance nécessaire
   aux certificats des modules maison.
4. Vérifier les signatures kmodigest des modules, puis signer le noyau final et
   l’UKI avec la clé persistante GLF, hors du build Nix.
5. Intégrer le shim signé Rocky et son MokManager, enrôler le certificat GLF,
   puis tester le démarrage avec Secure Boot actif et le chargement des modules.
6. Documenter les commandes, les résultats et les limites du prototype.

## Critères de validation

- Un noyau enrichi et une UKI signés GLF sont produits par la CI à partir d’une
  configuration versionnée, sans publication de clé privée.
- La publication Attic simulée produit un manifeste explicite sans aucun envoi.
- Le build utilise une révision verrouillée de NixOS unstable.
- Les `.cer` des modules sélectionnés sont récupérés depuis les sorties de
  génération de `kmodigest` et pris en compte dans la confiance du noyau.
- La cible démarre cette UKI avec Secure Boot effectivement actif.
- Le shim Rocky et son MokManager sont utilisés sans modification des binaires signés.
- L’enrôlement MOK du certificat GLF est validé sur la cible ; l’UKI signée GLF
  est acceptée après enrôlement et refusée en l’absence de toute confiance GLF.
- Les modules maison correctement signés se chargent sur le noyau cible.
- Un module non signé ou signé par une clé non approuvée est refusé dans la
  configuration de validation retenue.
- Une UKI dont la signature est invalide est refusée par la chaîne de démarrage.
- Les versions, empreintes des certificats et résultats des tests sont consignés.
- Les deux modules de référence sont construits pour le noyau cible et leur
  chargement est validé sous Secure Boot.
- Un paquet local supplémentaire et un paquet issu d’un dépôt Git externe peuvent
  être ajoutés par configuration, sans modifier le mécanisme central de l’UKI.
- Le cas d’une source Git sans définition Nix est validé avec une définition locale.
- Les révisions Git externes sont verrouillées ; un paquet ordinaire peut être
  ajouté indépendamment du parcours de signature des modules noyau.

## Conventions du dépôt

- Rédiger la documentation en français.
- Mettre à jour ce fichier lorsque des choix techniques sont arrêtés.
- Ne pas versionner les clés privées ni les secrets de signature ; leur stockage
  et leur utilisation devront être définis avant l’ajout du processus de signature.
- Les `.cer` sont des sorties générées à récupérer depuis le build ; leur copie
  manuelle dans le dépôt ne doit pas être un prérequis. Ils ne sont pas exclus
  globalement par `.gitignore`.
- Les sorties Nix `result` et `result-*` à la racine sont ignorées.
- Ne pas considérer une étape comme validée sans résultat de test consigné.
