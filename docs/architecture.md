# Architecture

NIX_SB contient des paquets, sans dépendance vers le code GLF-OS. Le choix de `kernelPackages` est centralisé dans `kernel.json`, avec une
révision nixpkgs verrouillée par ce dépôt. Le consommateur reprend cet ensemble.

```text
kernelPackages.kernel + drivers du catalogue
                    ↓
          pkgs/modules-tree (aggregateModules)
                    ├── pkgs/certificates : bundle + manifeste
                    └── pkgs/kernel : rebuildImage avec les certificats
```

`pkgs/kernel` produit une image (`bzImage` sur x86_64), pas un nouveau
`kernelPackages`. Les modules et l’initrd utilisent le noyau de base ; l’UKI
référence l’image enrichie. Recompiler les drivers contre cette image créerait
une dépendance circulaire. Le noyau de base doit réserver l’espace nécessaire
aux certificats selon le mécanisme kmodigest de nixpkgs.

L’arbre de confiance comprend les modules natifs et tout le catalogue, sans
lire `config.system.modulesTree`. Les paquets choisis doivent être construits
pour le même noyau. La liste des drivers installés reste une décision du
consommateur, indépendante de leur approbation dans le catalogue.

Le bundle et l’image reçoivent le même arbre via `default.nix`. Chaque paquet
est aussi importable individuellement ; dans ce cas le consommateur doit
fournir les mêmes `kernelPackages` et `approvedModules` aux deux paquets.

La chaîne de démarrage cible reste UEFI → shim Rocky → systemd-boot signé → UKI
signée. La confiance EFI et la confiance dans les modules sont distinctes.
Les paramètres `module.sig_enforce=1` et `lockdown=integrity` doivent être
présents dans l’UKI signée. Le signataire doit contrôler les composants approuvés ;
un catalogue local arbitraire ne constitue pas une autorisation de signature.

Les certificats du noyau sont générés par les builds. La clé privée EFI reste
extérieure aux paquets et au store Nix. Le provisionnement et le transport de
signature sont fournis par les workflows et le client de ce dépôt.
