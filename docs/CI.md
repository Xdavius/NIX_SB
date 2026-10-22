# Vérifications et builds

## Contrôles légers par défaut

`ci/check.sh` effectue les contrôles shell/YAML, l’évaluation de la flake avec
`--no-build`, et les tests Python du catalogue, du contrat de commande, du client GitHub
et des refus du bootstrap (sans génération de clé). Les assertions Nix testent les entrées invalides du catalogue,
la sélection du noyau et les définitions locales des drivers GLF et la cohérence de l’image avec le bundle.

```sh
nix develop .#ci --command bash ci/check.sh
```

Le shell peut télécharger ou construire ses outils, dont shim. Pour éviter
cette réalisation, lancer directement les commandes légères du README avec
les outils déjà installés. Les fichiers nouveaux non suivis par Git nécessitent
la référence `path:$PWD` (ou `GLF_FLAKE_REF="path:$PWD"` pour le script).

## Opérations explicites, hors contrôles légers

`ci/build.sh` construit les sorties du présent dépôt (`GLF_FLAKE_REF` permet de
choisir une référence). Il ne dépend plus d’une flake GLF-OS externe. Les images
non signées et le manifeste sont placés dans `dist/unsigned/`.
Le workflow GitHub lance ce build sur chaque push de branche et sur déclenchement
manuel. Les pull requests effectuent uniquement les contrôles légers.

Les tests `tests/test_boot.py` et `tests/test_signing_policy.py` utilisent de
vraies images PE et les variables `GLF_TEST_*` fournies par le shell `ci`.
`ci/test-signing.py "$GLF_TEST_STUB"` vérifie la signature avec une clé jetable.
Le test `tests/test_uefi.py` nécessite un noyau construit et le shell `vm`.
Ces tests ne sont pas lancés par `ci/check.sh`.

Les tests et builds réussis avant la refonte ne valident pas les nouveaux
chemins ni les drivers rapatriés. Un build et une validation Secure Boot seront
nécessaires séparément avant déploiement.

## Workflows de signature

`sign-request.yml` valide les images contre les builds de ce dépôt puis les signe
dans un job protégé séparé. `bootstrap-key.yml` crée la clé persistante une seule
fois. Ces workflows sont manuels, désactivés tant que leurs variables ne sont pas
activées, et ne sont pas exécutés par les contrôles légers. Voir SIGNING-SERVICE.md.

La passe de validation réelle du 22 octobre 2026 est consignée dans
[VALIDATION.md](VALIDATION.md), avec les commandes et les limites. Les scripts
`test_certificates.py` et `test_real_images.py` vérifient les artefacts construits.
Le test VM accepte `GLF_VM_VARIANT=xone` ou `xonedo` pour vérifier séparément les
variantes contre le même noyau de confiance. Ces opérations restent explicites.

## Une branche par version

Chaque branche (initialement `Rising`) conserve son choix de noyau, son catalogue,
sa version NVIDIA et son lock nixpkgs. La CI vérifie puis construit le commit poussé
sur cette branche ; les exécutions de branches différentes sont indépendantes.
Les artefacts sont nommés `unsigned-<branche>-<commit>` et contiennent `release.json`
avec branche, commit, sélection noyau, version NVIDIA et révision nixpkgs.
Les slashs du nom de branche sont remplacés par des tirets dans le nom d’artefact.

Les artefacts Actions restent conservés sept jours et ne constituent pas un cache
Nix permanent. Aucun transfert Attic ou publication de release automatique n’est
configuré. Le futur consommateur GLF-OS doit épingler la branche de sa version.
Les signatures de postes utilisent explicitement cette même branche protégée.
