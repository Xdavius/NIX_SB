# Architecture

NIX_SB contient des paquets, sans dépendance vers le code GLF-OS. Le choix de `kernelPackages` est centralisé dans `kernel.json`, avec une
révision nixpkgs choisie par les channels GLF-OS. La CI doit reprendre cet ensemble.
GLF-OS référence les sources dans glf-apps (flake = false) et appelle les paquets
via callPackage ; la flake interne NIX_SB n’est pas son interface.

```text
kernelPackages.kernel + drivers du catalogue
                    ↓
          pkgs/modules-tree (aggregateModules)
                    ├── pkgs/certificates : bundle + manifeste
                    └── pkgs/kernel : rebuildImage avec les certificats
```

`pkgs/kernel` produit une image (`bzImage` sur x86_64), pas un nouveau
`kernelPackages`. Les modules et l’initrd utilisent le noyau de base ; la CI
signe l’image enrichie. Recompiler les drivers contre cette image créerait
une dépendance circulaire. Le noyau de base doit réserver l’espace nécessaire
aux certificats selon le mécanisme kmodigest de nixpkgs.

L’arbre de confiance comprend les modules natifs et tout le catalogue, sans
lire `config.system.modulesTree`. Les paquets choisis doivent être construits
pour le même noyau. La liste des drivers installés reste une décision du
consommateur, indépendante de leur approbation dans le catalogue.

Le bundle et l’image reçoivent le même arbre via `default.nix`. Chaque paquet
est aussi importable individuellement ; dans ce cas le consommateur doit
fournir les mêmes `kernelPackages` et `approvedModules` aux deux paquets.

La chaîne de démarrage cible est UEFI → shim Rocky → systemd-boot signé → noyau
signé avec initrd séparé. La confiance EFI et la confiance dans les modules sont distinctes.
La politique noyau appartient à la configuration NixOS consommatrice. Le module
multiboot fourni conserve `module.sig_enforce=1` et `lockdown=integrity` par défaut,
mais l’installateur ne les impose pas : il conserve les paramètres de la génération.
L’initrd séparé et la ligne de commande ne sont pas authentifiés par cette chaîne
sans UKI ; les signatures EFI ne garantissent donc pas à elles seules une politique
de verrouillage choisie par le consommateur. Le signataire doit contrôler les composants approuvés ;
un catalogue local arbitraire ne constitue pas une autorisation de signature.

Les certificats du noyau sont générés par les builds. La clé privée EFI reste
extérieure aux paquets et au store Nix. Le provisionnement et la publication des
composants signés sont fournis par les workflows de ce dépôt. Aucun client de
signature n’est distribué aux postes. Voir integration-glfos.md à la racine.

## Consommation sans reconstruction du catalogue

La CI continue de construire le noyau avec **tous les certificats du catalogue**,
NVIDIA compris, puis de signer cette image. Aucune sélection par matériel ne
modifie le noyau publié ou son arbre de certificats.

`signed.consumerApi = 1` expose une consommation sans dépendance de build au
noyau reconstruit : `signed.bundle` vérifie le hash de l'archive, ses manifestes,
le certificat de production et les signatures, puis compare la première ligne
de `store-paths.txt` à l'identité Nix attendue du noyau. Cette identité est
évaluée sans réaliser la dérivation. Le consommateur fait confiance à la
publication épinglée pour l'association entre cette identité et l'image signée.
La signature seule n'atteste pas cette association.

Les métadonnées de démarrage référencent `signed.kernel`. Le contrôle explicite
`signed.verifiedBuild` reconstruit le catalogue complet et compare le contenu PE
à celui de la publication ; il ne fait pas partie du build des postes. La CI
vérifie également que signer les images ne modifie pas leur contenu PE.
Les pilotes activés sur le poste restent construits/installés normalement.
