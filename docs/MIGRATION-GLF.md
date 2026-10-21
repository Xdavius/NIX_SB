# Intégration native dans GLF-OS

Le code actif du prototype a été intégré à la branche GLF-OS
`feature/secureboot-uki`, dans `secureboot/`. `modules/default.nix` importe le
module directement. Aucun input NIX_SB ni patch glf-apps supplémentaire n'est
nécessaire dans la configuration des postes utilisant cette version GLF-OS.

Le noyau est défini une seule fois dans `secureboot/nix/kernel-packages.nix`,
partagé avec `modules/boot.nix`. Le catalogue contient les deux drivers maison,
NVIDIA open, xone, xpadneo, hid-tmff2 et v4l2loopback. NVIDIA utilise la même
définition pour le système et le catalogue. L'approbation d'un driver ne force
plus son activation sur tous les postes. Le correctif DEPMOD de v4l2loopback
évite une collision d'index pendant l'agrégation.

L'activation se fait par `iso-cfg/customConfig/secureboot-uki.nix`, à importer
explicitement. Le système doit suivre la révision unstable verrouillée par
`glf-os/glf-secureboot/nixpkgs`, conserver sa configuration matérielle et fournir
un jeton GitLab hors du store. Lire `secureboot/README.md` dans GLF-OS.

Le dépôt officiel retenu est `xdavius/glf-os`, branche dédiée
`feature/secureboot-uki`. Le signataire GitLab construit les composants approuvés
au commit de cette branche ayant déclenché le pipeline. La clé de production sera
créée une seule fois en CI, dans une variable protégée, masquée et cachée ; son
certificat public sera publié après validation. Le runner dédié reste à configurer.
L'ancien service GitHub est désactivé. Voir `secureboot/docs/CI.md` dans GLF-OS.

Les anciens répertoires nix/, pkgs/, integration/ et la flake de NIX_SB restent
comme banc de tests historique ; ils ne sont plus la source du build signé de
GLF-OS. Ne pas appliquer l'ancien patch integration/glf-os.patch sur la nouvelle
branche native.

Validation locale : évaluation de la configuration complète GLF-OS avec NVIDIA
et gaming ; tests des outils ; deadnix/statix ; construction réelle du noyau et
des modules ; présence des 21 certificats des sept paquets dans le bundle ;
démarrage QEMU Secure Boot avec le noyau complet, les deux drivers de volants
chargés et un module altéré refusé. Le fonctionnement du matériel physique et
le parcours de signature avec la clé persistante restent à valider après revue
et activation du signataire GitLab sur la branche dédiée.
