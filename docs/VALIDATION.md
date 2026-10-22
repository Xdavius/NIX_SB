# Validation réelle — 22 octobre 2026

## Résultats

- Build Nix réussi : noyau enrichi Linux 6.18.57, huit drivers du catalogue,
  bundle, outils glf-secureboot et UKI complète de la configuration fictive NixOS.
  Les sorties déjà disponibles dans le store ont été réutilisées ; xonedo,
  l’agrégation complète, l’image enrichie et l’UKI ont été construits pendant cette passe.
- 29 certificats de modules externes trouvés et présents dans le bundle, dont
  cinq NVIDIA 615.71.09, neuf xone et huit xonedo. Empreinte du bundle vérifiée.
- L’UKI complète passe la politique de signature (noyau, chargeur, reconstruction
  avec le stub approuvé). Noyau, systemd-boot et UKI signés avec une clé éphémère,
  signatures et contenu vérifiés ; clé supprimée après le test.
- Tests d’installation/rollback sur ESP simulée : 3 réussis. Politique de
  signature : 5 réussis. Script de signature : cas positifs et négatifs réussis.
- Trois démarrages QEMU/OVMF réussis : catalogue initial, variante xone, variante
  xonedo. Firmware Secure Boot actif, shim Rocky → systemd-boot signé → UKI signée,
  lockdown integrity actif. Module efivarfs altéré refusé avec « Key was rejected ».
- Dans chacune des deux variantes : chargement réussi de hid-fanatec,
  hid-logitech-new, hid_tmff_new, hid_xpadneo, v4l2loopback, xone_dongle et
  xone_gip_gamepad. Chaque variante utilise un arbre excluant l’autre paquet Xbox,
  mais le même noyau approuvant les huit drivers.

Le test VM utilise le vrai noyau enrichi avec un initrd minimal de test. L’UKI
NixOS complète a été construite et signée/vérifiée séparément ; son système
complet n’a pas été démarré. Aucun matériel de jeu ni GPU NVIDIA n’est émulé :
le chargement des modules testés ne prouve pas le fonctionnement des périphériques.
NVIDIA est construit et ses certificats contrôlés, pas chargé sur un vrai GPU.
L’enrôlement MOK est préparé dans le firmware de la VM, pas testé interactivement.
La CI distante, la clé persistante et les réglages GitHub n’ont pas été sollicités.
Aucun changement de démarrage de l’hôte ni modification GLF-OS.

## Artefacts locaux

- `result-validation` : image noyau enrichie.
- `result-validation-1` : bundle et manifeste des paquets approuvés.
- `result-validation-2` : outils.
- `dist/unsigned/` : UKI NixOS complète et images non signées, manifeste SHA256.
- `dist/uefi-serial.log` : premier démarrage.
- `dist/uefi-xone-serial.log`, `dist/uefi-xonedo-serial.log` : variantes testées.

SHA256 du noyau : `45cd9771c60d68d3677a08c0db2585107cef63ca286404fbce50c9a23d922920`.
SHA256 UKI complète : `af4a1fb29c425db97f54c85a86e1b68ab1df06ef43e1c0b64dfd4f1b62fe21e1`.
SHA256 modules.cer : `2e0ccbf770811974ceefe64d996b18a7f459520aa73944c21ce682b3e423e93b`.

## Reproduction

```sh
nix build "path:$PWD#kernel" "path:$PWD#certificates" "path:$PWD#boot-tools" \
  --max-jobs 1 --cores 2 --out-link result-validation
GLF_FLAKE_REF="path:$PWD" bash ci/build.sh
python3 tests/test_certificates.py result-validation-1
nix develop "path:$PWD#ci" --command python3 tests/test_boot.py
nix develop "path:$PWD#ci" --command python3 tests/test_signing_policy.py
nix develop "path:$PWD#ci" --command python3 tests/test_real_images.py dist/unsigned
nix develop "path:$PWD#vm" --command env GLF_VM_VARIANT=xone \
  python3 tests/test_uefi.py result-validation/bzImage
nix develop "path:$PWD#vm" --command env GLF_VM_VARIANT=xonedo \
  python3 tests/test_uefi.py result-validation/bzImage
```

## Correction révélée par le test

`ci/build.sh` échouait lors d’une seconde exportation : les fichiers copiés depuis
le store avaient conservé leur mode lecture seule. Les copies remplacent désormais
le fichier de destination, ce qui permet de relancer le build/export. L’export a
été relancé avec succès sur les anciens artefacts présents.
