# Migration vers le centre noyau/drivers

NIX_SB centralise désormais la famille noyau dans kernel.json, la version exacte
via le lock nixpkgs, les définitions de drivers GLF et le service de signature.
Aucune modification GLF-OS ni suppression des anciens dépôts n’est effectuée.

Le point d’entrée `pkgs.callPackage sourceNixSb {}` expose kernelPackages,
kernel (image enrichie), drivers, certificates, modulesTree, boot-tools et rocky-shim.
L’argument kernelPackages du point d’entrée racine est retiré : le choix appartient
à ce dépôt. La flake expose aussi cet ensemble dans legacyPackages.x86_64-linux.

Fanatec et new-lg4ff sont maintenus localement dans pkgs/drivers. La sous-flake,
son lock, les champs git/input du catalogue et le workflow de synchronisation
des anciens dépôts sont retirés. Les autres drivers peuvent provenir de nixpkgs.

Le service de signature et le bootstrap restent dans NIX_SB. Les anciens
workflows GitLab et le code GLF-OS ne sont pas modifiés par cette migration.
