# Catalogue de confiance GLF

`default.nix` est la liste explicite des modules externes approuvés. Elle contient
`hid-fanatek` (paquet amont hid-fanatecff) et `new-lg4ff`. Leurs définitions sont
reprises des checkouts GLF correspondants ; sources GitHub, versions et hashes
sont fixés dans chaque `default.nix`. Les compilations conservent la signature
kmodigest de nixpkgs et les certificats `.ko.cer`.

Le noyau approuvé contient les certificats de ses modules natifs et de **tout ce
catalogue**. La configuration d’un poste ne peut pas ajouter un certificat à ce
bundle via `boot.extraModulePackages` ou `system.modulesTree`. Les deux drivers
sont installés par le module GLF ; leur chargement dépend du matériel et de la
configuration. Aucun chargement forcé ou remplacement de driver natif n’est
imposé ici.

Pour approuver un driver Wi-Fi local :

1. Ajouter `pkgs/repo/mon-wifi/default.nix`, avec les sources locales versionnées
   ou une source Git à révision et hash verrouillés.
2. Le déclarer dans `pkgs/repo/default.nix` via `kernelPackages.callPackage`.
3. Construire, vérifier ses `.ko.cer`, tester son chargement et faire revoir la PR.
4. Fusionner sur la branche de signature, mettre à jour le verrouillage du poste,
   puis reconstruire et signer la nouvelle génération.

Copier un `.cer` dans ce dossier ne l’approuve pas. Un module supplémentaire hors
catalogue provoque une assertion. La signature distante vérifie indépendamment
le noyau et le chargeur contre les sorties construites depuis main, et reconstruit
l’UKI avec le stub approuvé pour détecter tout code EFI ajouté ou modifié.
Les paramètres de vérification des modules et de lockdown sont obligatoires.

Le noyau, les paquets et le catalogue doivent correspondre à la révision approuvée
par le service. Un autre noyau ou un overlay qui modifie les drivers exige aussi
une mise à jour revue du dépôt de signature. Les fichiers hardware-configuration,
la racine, l’initrd et les paramètres propres au poste restent spécifiques au poste.

Cette politique contrôle les images signées par ce service. Le propriétaire du
firmware conserve la possibilité de désactiver Secure Boot ou d’enrôler d’autres
clés MOK ; ce dépôt ne peut pas lui retirer ce contrôle physique.

La sortie `nix build .#certificates` contient `modules.cer`, `bundle.sha256` et
`approved-modules.json` : ce dernier répertorie le noyau et les paquets qui
alimentent le bundle. Le manifeste est également conservé par la CI de build.
