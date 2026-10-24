# Multiboot GLF intégré

Le module `modules/multiboot.nix` reprend le multiboot fourni dans
`/etc/nixos/customConfig/secureboot-multiboot/`. Les fichiers de cette configuration
et le démarrage de l’hôte ne sont pas modifiés par le développement du dépôt.
Voir [le raccordement GLF-OS](../integration-glfos.md#13-module-intégré-secure-boot-et-multiboot).

À l’import du module, `glf.secureboot.enable` vaut `true` et
`glf.multiboot.enable` vaut `false` : systemd-boot signé est donc le chemin par
défaut. `glf.secureboot.enable = false` permet de désactiver explicitement cette
intégration, sans modifier le réglage Secure Boot du firmware.

## Fonctionnalités conservées

| Fonction d’origine | Intégration |
| --- | --- |
| Fond et logo GLF | Assets repris dans `pkgs/multiboot-assets/assets` |
| Icônes et noms des autres OS | Entrées issues d’`efibootmgr --verbose`, avec détection de la distribution |
| Une entrée GLF au premier niveau | Entrée rEFInd avec `submenu_on_select true` ; Entrée ouvre les générations, Échap revient |
| Installation et retrait | `glf-multiboot install` et `remove`, plus hook NixOS automatique |
| Choix par défaut et délai | `glf.multiboot.makeDefault` et `timeout` |
| Respect des variables EFI | Aucune écriture NVRAM si `canTouchEfiVariables = false` |
| Protection des installations existantes | Marqueur `.glf-managed`, refus d’écraser un rEFInd non géré |
| Nettoyage ciblé | Entrées `glf-other-*` et commande explicite pour les anciens fichiers Lanzaboote |

La découverte concerne les entrées enregistrées dans le firmware, comme le module
d’origine ; ce n’est pas un scan exhaustif de tous les disques. Elles sont relues
à chaque installation. Si les variables EFI sont accessibles, elles peuvent être
lues même lorsque leur modification est interdite. L’identification des entrées
GLF tient compte de la partition, pour préserver celles d’un autre disque.

Le menu affiche les générations déjà installées dont la closure existe encore,
avec leur numéro et les informations disponibles dans leurs métadonnées.
La génération sélectionnée est la première, y compris après un rollback.
`configurationLimit = 10` limite l’affichage sans supprimer les générations.
Le délai démarre directement la génération sélectionnée ; seul le choix manuel
avec Entrée ouvre le sous-menu. Les autres OS conservent un démarrage direct.

## Signature et migration

La CI signe désormais rEFInd en plus du noyau et de systemd-boot. L’installateur
vérifie les signatures avant installation. Shim et MokManager restent inchangés.
La signature locale sbctl/Lanzaboote est remplacée par la signature centralisée :
aucune clé privée n’est requise sur le poste. Les réglages matériels/Plymouth de
l’ancien `boot.nix` restent du ressort de GLF-OS.

Le chemin multiboot est `EFI/refind/shimx64.efi`, avec rEFInd signé sous le nom
`grubx64.efi` attendu par shim. `EFI/GLF` conserve shim et systemd-boot signé.
Les noyaux signés et initrd séparés sont communs aux deux menus.
L’initrd et la ligne de commande ne sont pas authentifiés dans cette architecture.

Par défaut, le module installe `EFI/BOOT` seulement lorsque les écritures NVRAM
sont désactivées. `glf.multiboot.installFallback` permet de choisir explicitement.
En mode multiboot, un `EFI/BOOT` existant non vide et non marqué GLF est refusé :
conserver ce chemin avec `installFallback = false`, ou organiser sa migration
explicitement après identification de son propriétaire.

Une installation rEFInd issue de l’ancien module et portant `.glf-managed` peut
être remplacée par la nouvelle. Retirer son import pour éviter deux installateurs.
L’archive choisie doit contenir le nouveau rEFInd signé et correspondre à la même
révision NIX_SB ; une ancienne release ne suffit pas à activer le multiboot.

Pour désactiver durablement, conserver `glf.secureboot.enable = true` et mettre
`glf.multiboot.enable = false`. L’installation suivante restaure le chemin
systemd-boot avant de retirer le rEFInd géré. La commande `glf-multiboot remove`
fait cette opération ponctuellement ; elle ne change pas la configuration Nix.

Après avoir testé le nouveau démarrage, `glf-multiboot cleanup-lanzaboote`
supprime uniquement les fichiers historiques ciblés de Lanzaboote et exige une
installation GLF marquée. Aucun répertoire EFI partagé n’est supprimé en bloc.
Le nettoyage des anciennes entrées `glf-other-*` est automatique ; la commande
`cleanup-legacy-entries` reste disponible séparément.

## Validation et limites

Les tests couvrent la génération du menu, les limites d’affichage, le rollback,
le retrait, les fichiers non gérés, les signatures invalides et la gestion NVRAM
simulée. Le module NixOS est évalué activé et désactivé.

QEMU/OVMF démarre le menu produit par le véritable installateur, avec les assets
GLF, une clé MOK jetable et deux générations de test. Le parcours Entrée → Échap
→ Entrée → génération 41 démarre avec Secure Boot et lockdown integrity actifs ;
un module altéré est refusé. Ce test utilise un noyau/initrd de test commun :
il ne remplace pas un rollback entre deux systèmes GLF-OS complets sur matériel.

Le paquet compile rEFInd 0.14.2 avec le SDK EDK2 201903 pour ses anciennes
interfaces IntelFramework, et les BaseTools du channel. Le runtime de protection
de pile manque dans ce SDK ; cette protection est désactivée pour ce binaire.
Cette base de compilation doit être réévaluée avant déploiement de production.

Pour reproduire le test avec le noyau de validation déjà construit :

```sh
nix build "path:$PWD#testing-refind" --no-update-lock-file --out-link result-multiboot
nix build "path:$PWD#testing-boot-tools" --no-update-lock-file --out-link result-multiboot-tools
nix develop "path:$PWD#testing-vm" --no-update-lock-file --command env \
  GLF_VM_REFIND="$PWD/result-multiboot/share/efi/refind_x64.efi" \
  GLF_VM_INSTALLER="$PWD/result-multiboot-tools/bin/glf-secureboot-install" \
  GLF_VM_BOOT_MODE=split GLF_VM_VARIANT=xonedo \
  python3 tests/test_uefi.py result-validation/bzImage
```

Pour une fenêtre interactive, ajouter `GLF_VM_INTERACTIVE=1` et
`GLF_VM_QEMU=/chemin/vers/qemu-system-x86_64` avec un QEMU compilé avec GTK
(le QEMU minimal du shell de test ne fournit pas GTK). Aucun parcours clavier
n’est alors automatisé ; fermer la fenêtre termine la prévisualisation.

Le fond est désormais généré depuis `pkgs/multiboot-assets/assets/glf-bootloader.svg`
(contours vectorisés du PNG original, conservé comme référence). Le build produit
un PNG RGB opaque 8 bits, non entrelacé, en 1920 × 1080, sans métadonnées et avec
compression sans perte. Le logo du menu reste inchangé. La compression réduit
le fichier ; le tampon décodé reste de l’ordre de 8 Mio en RGBA. La validation
QEMU ne remplace pas un essai VMware.
