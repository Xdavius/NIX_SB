# Support d’enrôlement GLF — tests x86_64

Ce dossier fournit le shim signé de Rocky Linux 16.1-2.el10, son MokManager et
le certificat public **GLF-OS TEST ONLY Secure Boot**. Aucun secret n’est inclus.
Les binaires proviennent du même RPM officiel, verrouillé par SHA-256 dans
`pkgs/rocky-shim/default.nix`, et sont copiés sans modification.

## Construire ou télécharger

```sh
nix build .#enrollment --out-link result-enrollment
```

Cette construction est explicite et ne fait pas partie des contrôles légers.

```text
EFI/BOOT/BOOTX64.EFI       shim Rocky, valide par le firmware
EFI/BOOT/mmx64.efi        MokManager Rocky, valide par shim
EFI/BOOT/grubx64.efi      copie identique de MokManager pour ouvrir son menu
certificates/GLF-TEST.cer certificat public a enroler
info/                    signatures, SBAT et empreinte du certificat
SHA256SUMS               empreintes des fichiers deployes
```

Il s’agit d’un support d’enrôlement uniquement. Le fichier `grubx64.efi` n’est
pas GRUB : c’est MokManager sous le nom du second étage attendu par shim. Ce
support ne contient aucune UKI et ne démarre pas GLF-OS.

## Enrôler depuis une clé USB de test

1. Sur une clé USB de test disposant déjà d’une partition FAT32 amorçable en
   UEFI, copier **le contenu** du dossier de sortie à la racine. Les chemins
   `EFI/BOOT/BOOTX64.EFI` et `certificates/GLF-TEST.cer` doivent être conservés.
   Utiliser un support dédié pour ne pas remplacer son chargeur existant.
2. Démarrer cette clé via le menu de démarrage UEFI, avec Secure Boot actif.
   Le firmware doit accepter l’une des autorités Microsoft signant ce shim,
   et sa politique DBX/SBAT ne doit pas révoquer ces binaires.
3. Dans MokManager, choisir **Enroll key from disk**, sélectionner la partition
   USB puis `certificates/GLF-TEST.cer`.
4. Vérifier le sujet et l’empreinte affichés avec `info/GLF-TEST.txt`, puis
   confirmer l’enrôlement et redémarrer. Retirer la clé pour revenir au disque.

Cette action ajoute le certificat de test à MOK ; elle ne remplace pas les clés
UEFI PK/KEK/db. Le menu et l’amorçage doivent encore être validés sur une cible
UEFI : la construction du dossier ne prouve pas que le firmware l’acceptera.

## Variante : préparer la demande depuis Linux

Si `mokutil` est installé et que Linux a démarré en UEFI avec accès aux variables
EFI, il est possible de préparer une demande :

```sh
sudo mokutil --import certificates/GLF-TEST.cer
```

Définir un mot de passe temporaire, puis démarrer le **shim de ce support** au
redémarrage. Choisir **Enroll MOK**, vérifier le certificat et confirmer avec
ce mot de passe. Un redémarrage sur un autre chargeur qui ne lance pas shim ne
suffit pas à afficher cette demande. Une fois revenu sous Linux :

```sh
mokutil --test-key certificates/GLF-TEST.cer
```

Après les essais, retirer le certificat de test via `mokutil --delete` suivi
d’une confirmation dans MokManager. Ne pas utiliser `--reset`, qui vise toute
la liste MOK.

## Chaîne de démarrage GLF-OS à compléter

Le support fourni permet de préparer l’enrôlement. L’installation du shim et de
l’UKI signée sur l’ESP du poste, le choix du second étage et l’intégration à
`glf-update` restent distincts et non déployés ici. MokManager ne doit pas
rester le second étage de la chaîne normale de démarrage de GLF-OS.

Vérifications automatiques : empreinte du RPM, présence des signatures PE,
extraction des métadonnées SBAT, copies identiques des binaires et lecture du
certificat DER. La confiance du firmware, les révocations et l’enrôlement effectif
restent à tester sur la machine cible.

Source : [paquet officiel Rocky Linux](https://download.rockylinux.org/pub/rocky/10.2/BaseOS/x86_64/os/Packages/s/shim-x64-16.1-2.el10.x86_64.rpm).
