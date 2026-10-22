# Intégration GLF-OS Rising — noyau signé et initrd séparé

Ce guide décrit le raccordement à réaliser dans GLF-OS. Aucun fichier GLF-OS
n’est modifié par ce dépôt. Cible : x86_64, sans UKI et sans signature par poste.

## Organisation

La chaîne est : **firmware → shim Rocky → systemd-boot signé GLF → noyau signé
GLF + initrd local**. Le noyau et le chargeur sont signés une fois dans la CI ;
les postes téléchargent la même publication. L’initrd et les paramètres de
démarrage ne sont pas authentifiés dans ce mode.

| Élément | Responsable |
| --- | --- |
| Révisions nixpkgs et nixpkgs-unstable par version | `channels-glfos` |
| Famille noyau et définitions de pilotes | NIX_SB : `kernel.json`, `pkgs/drivers/` |
| Catalogue, définitions de pilotes, version NVIDIA | NIX_SB : `pkgs/drivers/` |
| Confiance des modules intégrée au noyau | NIX_SB : `sb.kernel` |
| Shim et MokManager avec leurs signatures originales | `sb.rocky-shim` |
| Certificat public GLF | `sb.secureboot-certificate` |
| Signature du noyau et de systemd-boot | CI NIX_SB, clé privée dans GitHub |
| Choix des pilotes, matériel, initrd, services | GLF-OS et `glf-apps` |
| Mises à jour des générations | `glf-update` pilote la mise à jour et appelle `glf-secureboot-install` |
| Installation des fichiers de démarrage signés | `glf-secureboot-install`, fourni par ce dépôt |

`glf-boot` reste le composant existant de GLF-OS ; la responsabilité des mises
à jour appartient à `glf-update`. Ce dépôt fournit le paquet
`glf-secureboot`, dont la commande d’installation ne demande aucun jeton GitHub.
Le client `glf-secureboot-sign` et son workflow de demandes sont supprimés.

## 1. Épingler une publication

La CI de chaque branche construit les composants. La signature exige une branche
protégée, `GLF_SIGNING_ENABLED=true` et une branche autorisée dans l’environnement
`glf-signing-production` (actuellement Rising). Le shim Rocky n’est pas resigné.

Chaque release publique contient :

- `glf-secureboot.tar.gz` : noyau signé, systemd-boot signé, shim, MokManager,
  certificat GLF PEM/DER, certificats des modules et manifestes.
- `release.json` : URL de l’archive, hash Nix, profil, branche et commit.
- `build.json` : versions et révisions de la construction.

Le tag contient le profil, le hash du nom de branche et le commit complet. La publication
refuse de remplacer une release existante. Le descripteur et son hash sont à
approuver dans GLF-OS ; ne pas récupérer implicitement une URL `latest` à chaque
évaluation. Les releases ne dépendent pas de la rétention de sept jours des
artefacts temporaires Actions, mais un administrateur peut toujours les supprimer.

## 1.1. Source référencée exclusivement dans glf-apps

[channels-glfos](https://framagit.org/gaming-linux-fr/glf-os/channels-glfos)
est l’autorité pour les révisions `nixpkgs` et `nixpkgs-unstable` de chaque version.
GLF-OS conserve ses entrées `glf-channels` et leurs `follows` existants. **Ne pas
ajouter de dépendance à la flake NIX_SB ni de `nixpkgs.follows = "nix-sb/nixpkgs"`.**
La flake de ce dépôt reste un outil interne de construction et de test.

Dans `modules/glf-apps/flake.nix`, ajouter seulement une source :

```nix
inputs.nix-sb-source = {
  url = "git+https://github.com/Xdavius/NIX_SB.git?ref=Rising";
  flake = false;
};
```

Le lock qui résout la sous-flake `glf-apps` fixe le commit source. Après publication,
versionner son descripteur dans `modules/glf-apps/secureboot/release.json` et
épingler le même commit que `release.json.commit`. Aucune publication sans UKI
n’est disponible tant que la refonte n’a pas été fusionnée et exécutée en CI.

Dans l’overlay existant de `glf-apps`, ajouter les attributs suivants en rendant
`nix-sb-source` accessible depuis les arguments `outputs` de la sous-flake :

```nix
# Fragment à intégrer à l’overlay existant, pas une seconde flake GLF-OS.
overlay = final: prev:
  let
    sb = prev.callPackage nix-sb-source {
      pkgs = prev;
      signedReleaseFile = ./secureboot/release.json;
    };
  in {
    glf-kernel-center = sb;
    glf-secureboot = sb.boot-tools;
    glf-secureboot-certificate = sb.secureboot-certificate;
    glf-kernel-signed = sb.signed.kernel;
    glf-bootloader-signed = sb.signed.bootloader;
    glf-rocky-shim = sb.rocky-shim;
    # Remplacent les deux définitions existantes dans cet overlay :
    new-lg4ff = sb.drivers.new-lg4ff;
    hid-fanatek = sb.drivers.hid-fanatecff;
  };
```

Ici `prev` est l’ensemble nixpkgs déjà choisi par GLF-OS via ses channels.
L’agrégateur `default.nix` ne lit ni n’évalue la flake ou le lock de NIX_SB :
il appelle les paquets locaux avec l’ensemble fourni. Utiliser le même ensemble
pour le noyau, les pilotes et systemd ; ne pas les répartir entre stable et
unstable sans politique explicite commune à la CI. Si le socle noyau doit venir
d’unstable, fournir cet ensemble issu de channels dans `glf-apps` et utiliser
exactement le même dans NIX_SB.

Les modules GLF-OS consomment ensuite l’overlay, sans connaître la source NIX_SB :

```nix
{ config, pkgs, ... }:
let
  sb = pkgs.glf-kernel-center;
in {
  # Sections suivantes à intégrer ici.
}
```

`glf-kernel-center` est un ensemble de paquets : ne pas l’ajouter à
`environment.systemPackages` ni aux sorties `packages` qui exigent une dérivation.
Les attributs individuels tels que `glf-secureboot` sont des dérivations.
Supprimer les anciens inputs Fanatec/new-lg4ff seulement après migration de leurs
usages vers ces références communes.

## 1.2. Deux canaux distincts

| Version GLF-OS | Dépôt channels | Publication à utiliser |
| --- | --- | --- |
| Actuelle | `glf-os-channels` | `release.json` avec `profile = "current"` |
| Testing | `testing-channels` | `release.json` avec `profile = "testing"` |

Les noms Git vérifiés sont `glf-os-channels.git` et `testing-channels.git`,
sous le groupe Framagit channels-glfos. Chacun fournit son couple nixpkgs et
nixpkgs-unstable. Testing n’est donc pas un synonyme de nixpkgs-unstable.

Les deux profils ont leurs propres paquets, artefacts et releases.
Temporairement, seule la CI testing est exécutée et requise pour fusionner :
current est signalé indisponible et ne produit aucun artefact ni release. Dans GLF-OS, conserver les
channels correspondant à la variante installée et choisir le descripteur du
même profil dans glf-apps. Le commit source NIX_SB peut être commun aux deux,
mais les publications signées ne sont pas interchangeables.

La CI utilise le nixpkgs de chaque profil pour noyau, pilotes et chargeur.
Les pins actuellement verrouillés sont :

- current : channels `dc9d3bd`, nixpkgs `26f4107`, unstable `55bfb4d` ;
- testing : channels `dbb24ff`, nixpkgs `02c087f`, unstable `9fbb54b`.

Le profil current reste bloqué : ses deux pins fournissent 6.18.56 sans
rebuildImage. Le socle testing fournit 6.18.57 avec rebuildImage et son évaluation
réussit. Une mise à jour du channel actuel ou un rétroportage reste nécessaire
pour sa publication ; la CI n’utilise pas testing à sa place. Aucun dépôt
channels n’a été modifié. Voir [les commandes CI par profil](docs/CI.md).

`sb.signed.bundle` télécharge l’archive par hash fixe et vérifie les signatures
avec le certificat épinglé dans NIX_SB. Il compare également shim et MokManager
aux originaux, et le contenu du noyau/chargeur à celui construit depuis le
nixpkgs fourni. Un overlay incompatible fait échouer la construction.

Sorties disponibles :

| Sortie | Contenu |
| --- | --- |
| `sb.signed.bundle` | Ensemble cohérent vérifié, utilisé par l’installateur |
| `sb.signed.kernel` | `bzImage` signé |
| `sb.signed.bootloader` | `share/efi/systemd-bootx64.efi` signé |
| `sb.secureboot-certificate` | `share/secureboot/GLF.pem` et `GLF.cer` |

Sans `signedReleaseFile`, `sb.signed` vaut `null` : aucun téléchargement implicite.
Les paquets de construction non signés restent utilisables pour développer et
pour la CI. Ce mécanisme n’est pas un cache binaire Nix des pilotes.

## 2. Noyau, pilotes et NVIDIA

```nix
boot.kernelPackages = sb.kernelPackages;
boot.kernelParams = [ "module.sig_enforce=1" "lockdown=integrity" ];
boot.extraModulePackages = [ sb.drivers.hid-fanatecff sb.drivers.xonedo ];
services.udev.packages = [ sb.drivers.hid-fanatecff ];
```

Cet exemple sélectionne seulement Fanatec et xonedo. Adapter les choix de
`glf-apps` au matériel :

| Pilote | Référence |
| --- | --- |
| Fanatec | `sb.drivers.hid-fanatecff` |
| Logitech force feedback | `sb.drivers.new-lg4ff` |
| Xbox xone ou xonedo | `sb.drivers.xone` **ou** `sb.drivers.xonedo` |
| Xbox Bluetooth | `sb.drivers.xpadneo` |
| Thrustmaster | `sb.drivers.hid-tmff2` |
| Caméra virtuelle | `sb.drivers.v4l2loopback` |

Ne pas installer tout le catalogue : xone et xonedo sont des alternatives avec
les mêmes noms de modules. Conserver les règles udev, firmwares, services et
blacklists nécessaires ; retirer les dépendances concurrentes qui ajoutent une
autre version du même pilote. Les noms du catalogue ne sont pas toujours ceux
de `modprobe`.

Pour le profil NVIDIA :

```nix
hardware.nvidia.package = sb.nvidia;
hardware.nvidia.open = true;
```

Autoriser NVIDIA non libre dans la politique nixpkgs existante. Conserver PRIME,
modesetting et gestion d’énergie. La version vient de NIX_SB ; ne pas ajouter
une seconde version des modules NVIDIA. Les anciens GPU incompatibles avec les
modules ouverts exigent un profil distinct qui n’est pas fourni ici.

## 3. Métadonnées de chaque génération

Le noyau de base reste `sb.kernelPackages.kernel` pour construire les modules
et l’initrd. Le noyau enrichi `sb.kernel` sert à vérifier la publication signée.
Supprimer le raccordement UKI de production et produire ces métadonnées v2 :

```nix
let
  metadata = pkgs.writeText "glf-secureboot.json" (builtins.toJSON {
    version = 2;
    signedBundle = "${sb.signed.bundle}";
    kernel = "${sb.kernel}/bzImage";
    initrd = "${config.system.build.initialRamdisk}/${config.system.boot.loader.initrdFile}";
    kernelParams = config.boot.kernelParams;
  });
in {
  system.systemBuilderCommands = ''
    ln -s ${metadata} "$out/glf-secureboot.json"
  '';
}
```

La génération doit aussi contenir `init`. L’installateur ajoute lui-même
`init=GENERATION/init`. Les paramètres doivent permettre de retrouver le système
racine et contenir exactement `module.sig_enforce=1` et `lockdown=integrity`.
Ne pas fournir un second `init=`. Le bundle est référencé par la génération,
ce qui conserve sa version lors d’un retour arrière.

## 4. Raccordement à glf-update

```nix
environment.systemPackages = [ sb.boot-tools ];
environment.etc."secureboot/GLF.pem".source =
  "${sb.secureboot-certificate}/share/secureboot/GLF.pem";
environment.etc."secureboot/GLF.cer".source =
  "${sb.secureboot-certificate}/share/secureboot/GLF.cer";
environment.etc."secureboot/install.json".text = builtins.toJSON {
  esp = "/boot"; # point de montage FAT réel de l’ESP
  certificate = "${sb.secureboot-certificate}/share/secureboot/GLF.pem";
  timeout = "5";
  canTouchEfiVariables = false; # adapter à la politique d’installation
};
```

`glf-update` construit la génération cible, puis appelle l’installateur avec les
outils et la configuration de cette génération. Il propage toute erreur et ne
déclare la mise à jour prête au démarrage qu’après succès :

```sh
glf-secureboot-install --config /chemin/config-generation/install.json "$generation"
```

Le chemin du JSON dans cet exemple est à raccorder à l’outil de mise à jour ;
`/etc/secureboot/install.json` désigne celui du système actif, pas nécessairement
celui d’une nouvelle génération. N’annoncer le démarrage disponible qu’après
succès. Ne pas lancer l’installateur standard systemd-boot/GRUB ensuite : il
pourrait remplacer les binaires signés. Le hook NixOS exact dépend du code GLF-OS.

L’installateur vérifie les deux signatures et la correspondance du noyau avant
les copies, puis installe :

- `EFI/GLF/generations/ID/kernel.efi` et `initrd` ;
- une entrée de type 1 dans `loader/entries/glf-ID.conf` ;
- shim et MokManager dans `EFI/GLF` et le chemin de secours `EFI/BOOT` ;
- systemd-boot signé sous `grubx64.efi`, nom attendu par shim ;
- le choix par défaut dans `loader/loader.conf`.

Avec `canTouchEfiVariables=false`, prévoir le chemin de secours UEFI ou une
entrée existante vers shim. Avec `true`, l’outil crée l’entrée GLF si nécessaire
et sélectionne la génération via bootctl. Garder ensemble les générations Nix,
leurs closures et les fichiers ESP nécessaires au rollback. Aucun nettoyage
automatique ni transaction globale contre une coupure pendant les copies.

## 5. Enrôlement et confiance

Enrôler une fois `GLF.cer` via MOK sur chaque machine. Son empreinte SHA256 :

```text
63:3F:DE:4E:91:1D:10:02:BB:D5:8B:39:45:D0:2B:C4:3F:1B:84:0E:6F:0D:5C:95:3B:57:3E:77:A6:56:BF:BF
```

Depuis Linux, `mokutil --import /etc/secureboot/GLF.cer` prépare la demande ;
confirmer dans MokManager au redémarrage **via shim**, puis vérifier avec
`mokutil --test-key /etc/secureboot/GLF.cer`. Le firmware doit accepter le shim
Rocky et ne pas le révoquer. Le binaire shim n’est jamais modifié pour y ajouter
GLF : cette confiance vient de MOK. La clé privée reste dans la CI.

La sortie historique `enrollment` de la flake reste un support **de test** avec
GLF-TEST : ne pas la distribuer comme support de production. Utiliser les
binaires de `rocky-shim` et le certificat de `secureboot-certificate` pour
préparer le support de production GLF-OS.

## 6. Mise à jour et validation

Pour chaque version GLF-OS : branche NIX_SB protégée et autorisée dans
l’environnement de signature. Publier après la CI, puis mettre à jour ensemble
les révisions de channels, le commit source résolu pour `glf-apps` et le
descripteur `release.json`. Aucun poste ne déclenche de
signature. Les anciens descripteurs restent utilisables tant que leurs releases
et les sources Nix restent disponibles.

Le démarrage sans UKI a été validé en VM avec Secure Boot actif, pilotes chargés,
rejet d’un module altéré et rejet d’un noyau altéré. Les tests de l’installateur
utilisent une clé jetable et un dossier temporaire. Il reste à valider la première
publication distante, le raccordement GLF-OS et le matériel réel, notamment
NVIDIA, les périphériques de jeu et l’enrôlement firmware.

Voir [VALIDATION](docs/VALIDATION.md), [CI](docs/CI.md) et
[signature centralisée](docs/SIGNING-SERVICE.md).
