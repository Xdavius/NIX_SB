# GLF-OS — Prototype UKI et Secure Boot

Ce dépôt prépare un prototype de noyau GLF-OS distribué sous forme d’**UKI
(Unified Kernel Image) signée**, destiné à démarrer avec **UEFI Secure Boot** et
à charger nos **modules noyau maison signés**.

Le prototype utilise exclusivement **NixOS unstable**, avec une révision de
`nixpkgs` verrouillée. GLF-OS reste la cible d’intégration.

Le dépôt principal est [glf-os](https://framagit.org/gaming-linux-fr/glf-os/glf-os).
Si sa configuration est nécessaire, utiliser la branche **`develop`** et
verrouiller un commit en cas d’intégration au build.

Le démarrage utilisera le **shim déjà signé de Rocky Linux** et son
**MokManager** pour enrôler le certificat public **GLF** via MOK. L’UKI sera signée
avec la clé GLF : le projet n’aura ainsi pas à faire signer son propre shim par
Microsoft. La version du shim et le parcours exact de chargement restent à valider.

Le travail inclut la prise en compte des certificats publics `.cer` associés aux
modules dans la confiance du noyau. D’après les précisions du projet, ces fichiers
sont générés par **`kmodigest` dans NixOS** : le prototype devra les récupérer
depuis le build, sans exiger leur ajout manuel au dépôt.
La signature de l’UKI et la validation des
signatures des modules constituent deux aspects distincts à configurer et tester.

## État du projet

Une flake NixOS unstable verrouillée et une CI GitHub Actions sont présentes.
**Les sorties actuelles de la CI concernent une machine fictive de test.**
L’UKI destinée à un poste doit être construite depuis sa propre configuration
`/etc/nixos#GLF-OS`, utilisée par `glf-update`. Voir
[INTEGRATION-GLF.md](docs/INTEGRATION-GLF.md).
Le prototype construit le noyau enrichi via `rebuildImage` et une UKI qui le
référence. La signature utilise une clé GLF persistante fournie par un environnement
GitHub protégé ; la publication Attic est simulée.

Les modules maison et le déploiement du shim restent à raccorder. Aucune clé GLF
n’est fournie, et aucun démarrage Secure Boot n’a été validé. Les instructions
d’activation et les limites de sécurité figurent dans [docs/CI.md](docs/CI.md).

## Objectifs du prototype

- Définir une configuration NixOS unstable reproductible pour le prototype GLF-OS.
- Assembler et signer une UKI contenant notamment le noyau et l’initrd.
- Intégrer les certificats nécessaires à la validation des modules maison.
- Permettre l’ajout déclaratif de paquets locaux ou issus de dépôts Git externes.
- Vérifier le démarrage avec Secure Boot actif et le chargement des modules signés.
- Vérifier le refus des signatures invalides ou non approuvées.

## Modules de départ et ajout de paquets

Les premiers modules à intégrer sont `hid-fanatek` (nom à vérifier dans la source)
et `new-lg4ff`, indiqués dans le dépôt
[app-glf-os](https://framagit.org/gaming-linux-fr/glf-os/app-glf-os).

Le prototype devra permettre d’ajouter d’autres modules noyau ainsi que des
paquets applicatifs ou utilitaires :

- depuis des définitions et sources présentes dans ce projet ;
- depuis l’URL d’un dépôt Git externe, avec une révision verrouillée et une
  définition de build Nix fournie par le dépôt ou écrite localement.

Les modules noyau devront être construits pour le noyau cible et suivre le
parcours de signature et de confiance des certificats. Les paquets ordinaires
seront intégrés au système selon leur usage ; leur ajout n’implique pas de les
embarquer dans l’UKI.

Sur un poste, les paquets se déclarent dans sa configuration NixOS, via
`boot.extraModulePackages` et `environment.systemPackages`. Le fichier
[tests/fixtures/machine.nix](tests/fixtures/machine.nix) ne sert qu’aux tests de CI. Les sources Git
s’ajoutent comme inputs verrouillés dans la flake. Les deux paquets maison restent
à raccorder à cette interface.

## Contenu du dépôt

| Fichier | Rôle |
| --- | --- |
| [flake.nix](flake.nix) | Sorties noyau, certificats et UKI ; outils de CI. |
| [.github/workflows/uki.yml](.github/workflows/uki.yml) | Validation, build manuel, signature et Attic simulé. |
| [docs/CI.md](docs/CI.md) | Configuration de la CI, secrets GLF et tests. |
| [CONTEXT.md](CONTEXT.md) | Contexte, décisions à prendre, plan et critères de validation. |
| [README.md](README.md) | Présentation et état du prototype. |
| [.gitignore](.gitignore) | Exclusion des sorties de build Nix `result` et `result-*` à la racine. |

## Prochaines étapes

Configurer l’environnement GitHub `glf-signing`, raccorder les modules maison et
lancer le build manuel. Valider ensuite le démarrage avec le shim Rocky,
l’enrôlement GLF et le chargement des modules sous Secure Boot.

La CI ne crée pas de nouvelle clé GLF. La clé existante reste hors du dépôt et du
store Nix. Le stockage GitHub Secrets est une première solution ; une clé non
exportable nécessitera un service de signature ou HSM contrôlé par GLF.

La clé GLF devra désormais être créée dans un service/HSM et rester **non
exportable**. La signature est désactivée sur GitHub en attendant cette
intégration ; le script PEM existant n’est pas la solution de production retenue.
