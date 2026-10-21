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
un jeton GitHub hors du store. Lire `secureboot/README.md` dans GLF-OS.

NIX_SB reste le service GitHub de signature et conserve la clé privée de test.
`ci/approved-source.json` fixe le commit GLF-OS dont les sorties sont autorisées.
Le client ne peut pas choisir cette référence. Le build manuel et la validation
des demandes utilisent cette source, y compris son stub et son ukify.
Une mise à jour nécessite une revue du commit GLF-OS et de la référence côté
signataire ; rien ne suit automatiquement la tête de develop.

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
et activation du workflow sur main.
