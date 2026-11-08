# Centre de drivers GLF

NIX_SB maintient directement vos définitions Fanatec et new-lg4ff, rapatriées
sans modification fonctionnelle des sources GLF précédemment verrouillées :

- hid-fanatecff : commit 9568d44d48cc7a6bc8d5be276ddbf394e9f65ff4 du dépôt GLF.
- new-lg4ff : commit 34b71eff7f73916c7b87dd89864215104766998d du dépôt GLF.

Le code des drivers est récupéré en amont par ces définitions, avec révision et
hash fixes. Les anciens dépôts de packaging ne sont plus des dépendances.

## Catalogue

```json
{
  "hid-fanatecff": { "path": "./hid-fanatecff" },
  "new-lg4ff": { "path": "./new-lg4ff" }
}
```

`path` charge une définition locale via le `callPackage` du noyau sélectionné.
Il est relatif au catalogue, commence par `./` et ne contient pas `..`.
Pour un driver nixpkgs, ajouter par exemple `"xpadneo": { "package": "xpadneo" }`.
`package` sélectionne un attribut de `kernelPackages` ; les attributs imbriqués
sont possibles avec des points. Chaque entrée doit contenir exactement un champ.

Pour ajouter un driver GLF, créer son dossier/default.nix et son entrée `path`.
Pour modifier une version, éditer directement la définition ici. Préserver
l’installation Kbuild, kmodigest et les certificats `.ko.cer`.
Les champs `git` et `input` ne sont plus pris en charge.

Tout le catalogue alimente la confiance du noyau. L’activation sur un poste reste
séparée. Après revue et contrôles légers, prévoir le build et la validation de
chargement avant déploiement. Aucun workflow ne modifie automatiquement les
versions ni ne fusionne des changements de driver.

## Catalogue GLF-OS et NVIDIA

Catalogue approuvé, issu du relevé GLF-OS `develop` et des ajouts demandés :

| Driver externe | Définition ici | Utilisation GLF-OS |
| --- | --- | --- |
| hid-fanatecff | locale | volants Fanatec |
| new-lg4ff | locale | volants Logitech |
| hid-tmff2 | nixpkgs | volants Thrustmaster |
| xone | nixpkgs | manettes Xbox |
| xpadneo | nixpkgs | manettes Xbox Bluetooth |
| xpad-noone | nixpkgs | variante xpad sans prise en charge Xbox One |
| openrazer | nixpkgs | périphériques Razer |
| xonedo | locale | variante xone pour dongle Xbox Wireless |
| v4l2loopback | nixpkgs avec DEPMOD=true | caméra virtuelle OBS |
| nvidia-open | mkDriver nixpkgs, version locale | GPU NVIDIA, open=true |

Les pilotes natifs (amdgpu, i915, ntsync, etc.) sont déjà dans l’arbre du noyau.
ZFS n’est pas activé dans le checkout GLF-OS relevé.
Les firmwares, pilotes d’impression et outils utilisateurs ne sont pas des
modules externes à ajouter au bundle de certificats. Leur activation reste côté
système (par exemple le firmware du dongle Xbox fourni par hardware.xone).

La version NVIDIA est désormais définie dans `pkgs/drivers/nvidia/version.json`,
avec tous ses hashes. Version initiale : 615.71.09, reprise de GLF-OS.
`sb.nvidia` fournit le paquet complet pour `hardware.nvidia.package` ;
`sb.drivers.nvidia-open` est exactement `sb.nvidia.open`, inclus dans la confiance.
Modifier la version une seule fois dans ce JSON. Aucun paquet propriétaire de
modules NVIDIA n’est approuvé par ce catalogue : le mode choisi est open=true.

Le paquet complet inclut des composants non libres. La flake les autorise
uniquement pour les paquets dont le nom commence par nvidia. Un consommateur
via callPackage doit configurer son nixpkgs en conséquence. L’évaluation ne
valide pas le téléchargement des sources, la compilation ni le matériel.

### Compléments utilisateurs NVIDIA 620

`pkgs/drivers/nvidia/install-extras.sh` complète le builder nixpkgs depuis
la même archive que les bibliothèques, sans changer les modules noyau :

- Vulkan SC : ICD dans `out/share/vulkansc/icd.d/nvidia_icd.json`, avec chemin
  absolu vers la bibliothèque ; compilateur `nvidia-pcc` dans `bin/bin`.
- NGX : `nvidia-ngx-updater` dans `bin/bin` et `nvngx_update.exe` dans
  `out/lib/nvidia/wine`. Les exécutables Linux ont un interpréteur et un RPATH Nix.
- Inventaire amont : `bin/share/nvidia/files.d/sandboxutils-filelist.json`,
  conservé avec son schéma original. Ce fichier n’est pas un inventaire des
  chemins absolus du store Nix.

Le contrôle d’installation intégré vérifie ces fichiers, les dépendances ELF
des nouveaux outils, la cible de l’ICD Vulkan SC et les liens symboliques.
Le complément ne remplace aucun fichier ou lien déjà installé par nixpkgs.
Un fichier amont invalide fait échouer le contrôle ; il n’est pas écrasé pour
masquer le problème. Les hooks et contrôles préexistants de nixpkgs sont conservés.

Chaque build écrit `out/nix-support/nvidia-extras.json` et affiche son contenu
dans les logs : `addedByNixSb` liste les ajouts locaux, `providedByNixpkgs` les
éléments déjà fournis et `upstreamComplete` indique si aucun ajout n’était requis.
Après un build réussi avec `upstreamComplete: true`, le complément local devient
candidat au retrait. Ce diagnostic concerne les fichiers contrôlés, indépendamment
du numéro du pilote proposé par défaut dans nixpkgs ; il ne remplace pas les
tests GPU et conteneurs. Il ne signifie pas qu’il faut retirer le choix de version
dans `version.json`.

Pour consulter le rapport du paquet construit :

```sh
nix build --no-update-lock-file "path:$PWD#testing-upstream-latest-nvidia" --out-link result-nvidia
cat result-nvidia/nix-support/nvidia-extras.json
```

Le test léger `python3 -m unittest discover -s tests -p test_nvidia_extras.py`
couvre notamment la prise en charge amont partielle/complète et deux exécutions
successives. La provenance est conservée lors de la seconde exécution pour éviter
de prendre nos propres ajouts pour un support natif de nixpkgs.

Le contrôle d’installation ne lance ni mise à jour NGX ni application GPU.
NGX reste désactivé par défaut ;
son activation utilise la configuration documentée par NVIDIA, notamment
`__NGX_CONF_FILE` ou `$XDG_CONFIG_HOME/nvidia-ngx-conf.json` et un répertoire de
modèles accessible en écriture. Voir [la documentation NGX de NVIDIA](https://download.nvidia.com/XFree86/Linux-x86_64/620.70.06/README/ngx.html).

Le module NixOS expose déjà `sb.nvidia.bin` dans les paquets système et
`sb.nvidia.out` dans les paquets graphiques. L’ajout des fichiers ne valide
pas leur utilisation dans des conteneurs : la découverte de l’inventaire et les
montages CDI restent à tester sur un poste avec le module NVIDIA Container Toolkit.
Vulkan SC requiert aussi un test avec un chargeur/application Vulkan SC ; il est
distinct du Vulkan utilisé par les jeux. Voir [les composants installés par NVIDIA](https://download.nvidia.com/XFree86/Linux-x86_64/620.70.06/README/installedcomponents.html).

Ce catalogue approuve dix drivers ; il n’impose pas de tous les activer.
La fixture de test les agrège tous pour vérifier la cohérence des certificats.

## xonedo

Ajout local de [OpenGamingCollective/xonedo](https://github.com/OpenGamingCollective/xonedo),
commit `982cbcb019ae4d2bee5ae69385223409ee555c88`.
Le build utilise directement Kbuild et modules_install pour
préserver kmodigest, sans exécuter les scripts DKMS ou télécharger un firmware
pendant l’installation.

xonedo vise le dongle Xbox Wireless et conserve xpad. Ses modules portent les
mêmes noms `xone_*` que xone : choisir xone OU xonedo sur un poste, pas les deux.
Les fichiers xonedo sont installés dans `extra/xonedo` pour éviter les collisions
de chemins dans le catalogue de confiance commun. Ce catalogue approuve les deux
variantes ; son index depmod ne doit pas servir à choisir la variante du poste.
La fixture de test n’est pas une configuration matérielle à déployer.
Le firmware du dongle et l’activation restent à gérer côté consommateur.
La compilation et l’agrégation réelles restent à valider lors des tests lourds.

## xpad-noone et openrazer

Ces deux entrées réutilisent `kernelPackages.xpad-noone` et
`kernelPackages.openrazer` du noyau sélectionné, avec les versions et sources
fixées par le channel résolu. Leur ajout étend l’arbre des modules et la collecte
des certificats ; il ne les active pas automatiquement sur les postes.

xpad-noone fournit une variante de xpad sans prise en charge Xbox One.
Son activation côté NixOS implique de mettre le module natif `xpad` en blacklist.
OpenRazer fournit les modules Razer ; son daemon, ses règles udev et les droits
utilisateurs restent à configurer côté consommateur. Le paquet du catalogue
peut être fourni à `hardware.openrazer.packages.kernel`.
