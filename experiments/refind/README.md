# Essai rEFInd : ouvrir les générations avec Entrée

Branche `experiment/refind-generation-submenu`. Le prototype est maintenant intégré au paquet
`testing-refind`, à l’installateur et à la chaîne de publication.
Voir [le module multiboot](../../docs/MULTIBOOT.md).

Le patch ajoute `submenu_on_select true` dans une entrée manuelle rEFInd.
Valider cette entrée ouvre son sous-menu existant ; Échap revient au menu
principal. Sans cette option, le démarrage direct reste le comportement normal.
Le démarrage automatique après expiration du délai reste également inchangé.

```text
menuentry "GLF-OS" {
    loader \EFI\GLF\generations\current\kernel.efi
    initrd \EFI\GLF\generations\current\initrd
    options "... init=/nix/store/.../init"
    submenu_on_select true
    submenuentry "Generation precedente" {
        loader \EFI\GLF\generations\previous\kernel.efi
        initrd \EFI\GLF\generations\previous\initrd
        options "... init=/nix/store/.../init"
    }
}
```

Cet exemple est un schéma, pas une configuration installable. Le prototype VM
utilise deux entrées fictives partageant le même noyau et le même initrd de test,
avec des paramètres distincts pour vérifier le choix effectué. Il ne teste pas
encore le rollback entre deux systèmes GLF-OS complets.

## Compilation

Sources rEFInd **0.14.2**, archive amont vérifiée par hash, avec un patch local.
Compilation **TianoCore EDK2**, pas GNU-EFI. Le SDK `edk2-stable201903` fournit
les interfaces IntelFramework encore utilisées par rEFInd ; les BaseTools
proviennent du channel Nix utilisé pour la compilation.

Les protections de pile activées par les BaseTools modernes sont désactivées
pour cette compilation expérimentale, car leur runtime manque dans le SDK
historique. Les sections PE sont alignées sur 4096 octets, y compris SBAT :
sans cet alignement, le premier essai échouait avant le menu sous shim/OVMF.
Ce SDK ancien et les options de compilation devront être réévalués avant une
intégration de production.

```sh
nix flake update --flake "path:$PWD" --refresh
nix build "path:$PWD#testing-refind" --no-update-lock-file --out-link result-refind
```

## Essai isolé

Réutiliser un noyau enrichi déjà construit, ici `result-validation/bzImage` :

```sh
nix develop "path:$PWD#testing-vm" --no-update-lock-file --command env \
  GLF_VM_REFIND="$PWD/result-refind/share/efi/refind_x64.efi" \
  GLF_VM_BOOT_MODE=split GLF_VM_VARIANT=xonedo \
  python3 tests/test_uefi.py result-validation/bzImage
```

Le test crée une ESP et un firmware temporaires, signe rEFInd et le noyau avec
une clé jetable inscrite dans MOK, puis démarre via shim Rocky. QMP envoie
Entrée, Échap, Entrée, Bas, Bas, Entrée et vérifie `glf_generation=41`,
Secure Boot, lockdown et le rejet d'un module altéré. Ajouter
`GLF_VM_REFIND_CHOICE=other` teste le démarrage direct de l'autre entrée.

Captures réelles : `dist/refind-preview/*.ppm` ; journal série :
`dist/uefi-xonedo-refind-serial.log` (suffixe `-other` pour l'autre entrée).
Les captures et journaux ne sont pas versionnés.

Les deux assets de `../../pkgs/multiboot-assets/assets/` sont copiés depuis le dossier fourni par l'utilisateur,
`/etc/nixos/customConfig/secureboot-multiboot/assets/` : logo et fond GLF existants.
Le dossier d'origine et le démarrage de l'hôte ne sont pas modifiés.

La génération des entrées installées, la découverte des entrées firmware et la
signature en CI sont intégrées. Aucune clé de production n’est utilisée par ces tests.

## Résultats du 24 octobre 2026

Compilation via `testing-refind` réussie (BaseTools EDK2 202608).
Deux parcours QEMU/OVMF réussis avec le binaire final : sélection directe de
l'autre entrée et ouverture/retour/sélection de la génération fictive 41.
Dans les deux cas : Secure Boot=1, lockdown integrity, chargement des pilotes
de la variante xonedo et rejet du module altéré. Les captures montrent une
seule icône GLF au menu principal, puis une liste dans son sous-menu.
La compilation Python des scripts et `git diff --check` passent également.
Le démarrage sur firmware physique et le rollback GLF-OS complet restent à tester.
