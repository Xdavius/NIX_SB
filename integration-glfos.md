# Intégration de NIX_SB dans GLF-OS Rising

Ce document décrit les changements à réaliser dans GLF-OS. Il ne les applique
pas. Les exemples concernent `x86_64-linux` et doivent être raccordés aux modules
existants de GLF-OS, notamment `glf-apps`, `glf-boot` et l’outil de mise à jour.

## 1. Répartition des responsabilités

| Élément | Responsable |
| --- | --- |
| Famille du noyau | NIX_SB : `kernel.json` |
| Révision nixpkgs et version exacte du noyau | NIX_SB : `flake.lock` |
| Catalogue, définitions et versions des pilotes | NIX_SB : `pkgs/drivers/` |
| Version NVIDIA, modules et composants utilisateur associés | NIX_SB : `pkgs/drivers/nvidia/` |
| Image noyau enrichie des certificats des modules approuvés | NIX_SB : `sb.kernel` |
| Clé privée et signature des images EFI | CI NIX_SB |
| Sélection des pilotes installés | GLF-OS / `glf-apps` |
| Matériel, initrd, paramètres de démarrage, PRIME, services, firmware | GLF-OS |
| Assemblage et installation de chaque génération | GLF-OS appelle `glf-secureboot-install` |

Conserver `glf-boot` dans GLF-OS. Le paquet de ce dépôt s’appelle
`glf-secureboot` et fournit les commandes `glf-secureboot-install` et
`glf-secureboot-sign`. Il n’expose pas un module NixOS prêt à importer.

## 2. Dépendance de version et nixpkgs

Ajouter une entrée flake et faire suivre le nixpkgs choisi par NIX_SB :

```nix
inputs.nix-sb.url = "github:Xdavius/NIX_SB/Rising";
inputs.nixpkgs.follows = "nix-sb/nixpkgs";
```

Le `flake.lock` de GLF-OS fixe ensuite un commit précis de Rising. Le nom de
branche seul ne déclenche pas de mise à jour automatique des postes.

Dans la construction de la configuration NixOS, transmettre `inputs` via
`specialArgs` si ce n’est pas déjà fait, puis créer l’ensemble de paquets :

```nix
# Dans un module GLF-OS recevant inputs via specialArgs.
{ pkgs, inputs, ... }:
let
  sb = pkgs.callPackage inputs.nix-sb.outPath {};
in {
  # Configuration décrite dans les sections suivantes.
}
```

`callPackage` utilise le `pkgs` fourni par GLF-OS. Les overlays ou overrides
modifiant le noyau, les pilotes, systemd ou le stub peuvent produire des images
que la CI refuse, même avec le même lock. Éviter ces divergences ; porter les
changements correspondants dans NIX_SB.

Autre possibilité : `sb = inputs.nix-sb.legacyPackages.x86_64-linux;` pour
reprendre directement ses paquets. Les composants utilisés pour construire
l’UKI doivent toujours correspondre à ceux de la CI.

## 3. Noyau et sélection des pilotes

Le module commun doit utiliser :

```nix
boot.kernelPackages = sb.kernelPackages;
boot.kernelParams = [ "module.sig_enforce=1" "lockdown=integrity" ];
# Si GLF-OS utilise également le constructeur UKI de NixOS :
boot.uki.settings.UKI.Linux = "${sb.kernel}/bzImage";
```

`sb.kernelPackages.kernel` reste le noyau de base pour construire l’initrd et
les modules. `sb.kernel` est son image enrichie pour le démarrage ; ne pas
l’affecter directement à `boot.kernelPackages`.

Adapter les choix de `glf-apps` aux références suivantes :

| Choix GLF-OS | Paquet à sélectionner |
| --- | --- |
| Fanatec | `sb.drivers.hid-fanatecff` |
| Logitech force feedback | `sb.drivers.new-lg4ff` |
| Xbox, variante xone | `sb.drivers.xone` |
| Xbox, variante xonedo | `sb.drivers.xonedo` |
| Xbox Bluetooth | `sb.drivers.xpadneo` |
| Thrustmaster force feedback | `sb.drivers.hid-tmff2` |
| Caméra virtuelle | `sb.drivers.v4l2loopback` |
| NVIDIA ouvert | `sb.nvidia` via le module NVIDIA, voir ci-dessous |

Exemple pour un profil ayant choisi Fanatec et xonedo :

```nix
boot.extraModulePackages = [
  sb.drivers.hid-fanatecff
  sb.drivers.xonedo
];
services.udev.packages = [ sb.drivers.hid-fanatecff ];
```

Ne pas installer `builtins.attrValues sb.drivers` sur tous les postes : le
catalogue représente les pilotes approuvés, pas une sélection matérielle.
`xone` et `xonedo` fournissent les mêmes noms de modules : proposer un choix
exclusif et retirer l’ancienne variante lors du changement.

Conserver et vérifier les règles udev, chargements de modules, firmwares,
blacklists et services des profils actuels. Éviter qu’un module NixOS existant
ajoute en parallèle sa propre version d’un pilote remplacé ici. Les noms du
catalogue ne sont pas nécessairement les noms à passer à `modprobe`.

Les anciennes dépendances aux dépôts de paquets Fanatec/new-lg4ff peuvent être
retirées de GLF-OS après migration de leurs usages vers NIX_SB. Les définitions
sont gérées ici ; elles peuvent encore télécharger les sources amont épinglées.

## 4. NVIDIA

Dans le profil NVIDIA uniquement :

```nix
hardware.nvidia.package = sb.nvidia;
hardware.nvidia.open = true;
```

Autoriser les paquets NVIDIA non libres dans la politique nixpkgs existante.
Conserver les réglages GLF-OS de PRIME, modesetting, gestion d’énergie et services.
Le module NVIDIA NixOS sélectionne les modules associés au paquet ; ne pas
ajouter une deuxième version de NVIDIA dans `boot.extraModulePackages`.

Supprimer les choix de version et hashes NVIDIA concurrents dans GLF-OS.
Une mise à jour passe par `pkgs/drivers/nvidia/version.json` dans NIX_SB, puis
par la mise à jour du lock de GLF-OS. Les anciens GPU incompatibles avec les
modules ouverts nécessitent un autre profil explicitement pris en charge ; le
catalogue actuel ne constitue pas une prise en charge de toutes les générations.

## 5. Métadonnées de chaque génération

`glf-secureboot-install` attend une génération NixOS contenant `init`,
`etc/os-release` et `glf-secureboot.json`. Ajouter ce dernier à la construction
du système, avec les chemins de la génération concernée :

```nix
# À intégrer dans un module ayant config, pkgs et sb à disposition.
let
  bootMetadata = pkgs.writeText "glf-secureboot.json" (builtins.toJSON {
    version = 1;
    kernel = "${sb.kernel}/bzImage";
    initrd = "${config.system.build.initialRamdisk}/${config.system.boot.loader.initrdFile}";
    stub = "${pkgs.systemd}/lib/systemd/boot/efi/linuxx64.efi.stub";
    systemdBoot = "${pkgs.systemd}/lib/systemd/boot/efi/systemd-bootx64.efi";
    ukify = "${pkgs.systemdUkify}/lib/systemd/ukify";
    kernelVersion = sb.kernelPackages.kernel.modDirVersion;
    kernelParams = config.boot.kernelParams;
  });
in {
  system.systemBuilderCommands = ''
    ln -s ${bootMetadata} "$out/glf-secureboot.json"
  '';
}
```

Vérifier que les paramètres effectifs permettent de retrouver le système racine
et incluent une seule fois `module.sig_enforce=1` et `lockdown=integrity`.
L’installateur ajoute lui-même `init=CHEMIN_GENERATION/init`.
L’initrd reste celui de la machine ; ne pas utiliser la sortie `.#uki` de NIX_SB,
qui est construite pour une machine fictive.

## 6. Certificat et configuration de l’installateur

Livrer les fichiers publics depuis la révision NIX_SB verrouillée :

```nix
environment.systemPackages = [ sb.boot-tools ];
environment.etc."secureboot/GLF.pem".source =
  "${inputs.nix-sb}/certificates/production/GLF.pem";
environment.etc."secureboot/GLF.cer".source =
  "${inputs.nix-sb}/certificates/production/GLF.cer";
```

Créer un JSON de configuration, par exemple avec `builtins.toJSON`, contenant :

| Champ | Valeur à fournir |
| --- | --- |
| `esp` | Point de montage réel de l’ESP, par exemple `/boot` |
| `certificate` | Chemin vers le `GLF.pem` approuvé |
| `shim` | `"${sb.rocky-shim}/share/efi"` |
| `signerCommand` | Liste d’arguments du client de signature |
| `timeout` | `"5"`, délai du menu de démarrage |
| `canTouchEfiVariables` | Booléen selon la politique d’installation GLF-OS |

Pour un essai contrôlé avec le transport GitHub actuel :

```nix
signerCommand = [
  "${sb.boot-tools}/bin/glf-secureboot-sign"
  "--repo" "Xdavius/NIX_SB"
  "--ref" "Rising"
  "--token-file" "/run/secrets/glf-signing-github-token"
  "--timeout" "28800"
];
```

Le jeton est fourni à l’exécution, jamais écrit dans le store Nix. Il doit
permettre les uploads de draft releases, le déclenchement du workflow et la
récupération des artefacts. Ne jamais distribuer la clé privée ni le jeton de
provisionnement des secrets GitHub.

**Point à résoudre avant déploiement général :** NIX_SB est public. Le client
refuse l’envoi par défaut ; `--allow-public-artifacts` autorise explicitement la
publication potentielle de l’initrd dans les artefacts. Cette option n’a été
validée qu’avec des images fictives et ne doit pas être ajoutée automatiquement
aux postes. Prévoir un transport privé ou un service de signature avec une
identité et des permissions limitées par poste, ou construire centralement les
configurations machines. Le client GitHub actuel n’est pas un service anonyme
de distribution pour toute une flotte.

## 7. Raccordement à glf-boot et aux mises à jour

Après construction de la génération cible, appeler :

```sh
glf-secureboot-install --config /etc/secureboot/install.json "$generation"
```

`generation` doit être le chemin absolu de la nouvelle génération. Le fichier
`install.json` est celui produit à l’étape précédente. Utiliser les outils et
la configuration correspondant à cette génération lors d’une mise à jour.

L’intégration doit :

1. Construire la génération et conserver une génération de secours.
2. Assembler puis soumettre ses images à la signature via cette commande.
3. Attendre le succès et propager toute erreur à l’outil de mise à jour.
4. Déclarer le nouveau démarrage disponible seulement après installation réussie.

La commande vérifie les signatures et le contenu des images avant d’installer
l’UKI dans `EFI/Linux`, shim et MokManager dans `EFI/GLF` et `EFI/BOOT`, ainsi
que systemd-boot signé sous le nom `grubx64.efi` attendu par shim. Elle écrit
également `loader/loader.conf`. Les anciennes UKI sont conservées.

Raccorder ce chemin au mécanisme d’installation du chargeur utilisé par GLF-OS,
y compris lors des installations initiales, mises à jour et retours arrière.
Éviter qu’un installateur systemd-boot/GRUB standard réécrive ensuite ces fichiers
avec un chargeur non signé. Le simple ajout de `boot.uki.settings` ne réalise
pas ce raccordement. Le choix exact du hook dépend du code GLF-OS existant.

Prévoir la rétention des générations Nix et des UKI sur l’ESP ensemble : conserver
une UKI ne suffit pas si le système qu’elle référence a été supprimé du store.
L’installateur ne fait aucun nettoyage automatique des anciennes UKI et n’offre
pas de transaction globale en cas de coupure pendant les copies sur l’ESP.

## 8. Enrôlement et premier démarrage

Enrôler le certificat de production `GLF.cer` via MokManager sur chaque machine.
Son empreinte SHA256 est :

```text
63:3F:DE:4E:91:1D:10:02:BB:D5:8B:39:45:D0:2B:C4:3F:1B:84:0E:6F:0D:5C:95:3B:57:3E:77:A6:56:BF:BF
```

La demande peut être préparée depuis Linux avec
`mokutil --import /etc/secureboot/GLF.cer`, puis confirmée physiquement dans
MokManager au démarrage via shim. Vérifier ensuite avec
`mokutil --test-key /etc/secureboot/GLF.cer`.

L’approbation GitHub supprimée pour la signature n’élimine pas cette confirmation
locale d’enrôlement. La sortie `.#enrollment` actuelle contient le certificat
**de test** : préparer un support de production distinct avec `GLF.cer`.
Le firmware doit accepter le shim Rocky fourni et sa politique de révocation.

Chaîne attendue : firmware → shim Rocky → systemd-boot signé → UKI signée.
Les certificats de modules de `sb.certificates` sont distincts du certificat EFI
GLF ; leur confiance est intégrée à l’image noyau enrichie.

## 9. Mises à jour et branches

Pour Rising, mettre à jour NIX_SB par PR, attendre sa CI, puis mettre à jour
l’entrée `nix-sb` du lock GLF-OS et tester la génération résultante.
La signature reconstruit les composants du commit exécuté de `Rising` : le
client actuel transmet une branche, pas le commit du lock GLF-OS. Si Rising a
avancé avec des composants différents, une ancienne génération peut être
refusée. Coordonner les révisions ; la signature de révisions historiques reste
à prévoir avant de garantir la reconstruction/signature de toutes les versions.

Pour une nouvelle version GLF-OS : créer sa branche NIX_SB, la protéger, adapter
l’input GLF-OS et `--ref`, puis autoriser explicitement cette branche dans
l’environnement GitHub de signature. Actuellement, cet environnement autorise
Rising. Réutiliser la clé GLF existante, sans relancer le bootstrap.

La CI par branche construit des artefacts ; elle ne fournit pas encore un cache
Nix binaire ni une publication permanente d’images signées. Les réponses aux
demandes de signature sont conservées sept jours sur GitHub.

## 10. Validation avant livraison

Commencer par l’évaluation de la configuration GLF-OS puis la construction d’une
génération pilote. Vérifier les paquets réellement sélectionnés, l’absence de
doublon xone/xonedo et les métadonnées de cette génération. Tester ensuite :

- Signature et installation dans une VM UEFI dédiée, avec transport approuvé.
- Secure Boot actif, chargement des pilotes choisis et rejet d’un module altéré.
- Redémarrage sur la nouvelle génération et retour à la précédente.
- Échec de signature ou indisponibilité réseau sans annonce de mise à jour réussie.
- Matériel réel : GPU NVIDIA, périphériques de jeu et particularités du firmware.

Le test [39766464511](https://github.com/Xdavius/NIX_SB/actions/runs/39766464511)
a validé la signature automatique avec la clé de production de trois images
fictives, leur téléchargement et la vérification locale de leurs signatures.
Cela ne valide pas encore l’intégration GLF-OS, le démarrage d’un poste réel ni
le transport des initrd réels. Les essais VM précédents sont décrits dans
[docs/VALIDATION.md](docs/VALIDATION.md).

Références d’implémentation : [API des paquets](docs/usage.md),
[installateur](pkgs/boot-tools/src/install_boot.py),
[client de signature](pkgs/boot-tools/src/github_sign.py),
[politique de validation](pkgs/boot-tools/src/signing_policy.py).
