# UKI de la machine GLF-OS

## Configuration faisant autorité

Le `glf-update` installé sur le poste utilise `/etc/nixos#GLF-OS` pour construire
et installer le système. L’UKI doit être dérivée de cette même configuration
NixOS : matériel, disques, initrd, paramètres noyau, modules et chemin `init` du
système construit. Elle ne doit pas provenir d’une machine générique de la CI.

`nix/secure-boot.nix` est un **module NixOS complémentaire** : il ajoute les
options de vérification des modules, le noyau enrichi des certificats et la
référence à ce noyau dans l’UKI. Il conserve le choix de `boot.kernelPackages`
de la machine. Il est exporté sous `nixosModules.secureBoot` et
`nixosModules.default`.

`tests/fixtures/machine.nix` est une **machine fictive réservée aux tests**. C’est
l’ancien `project.nix`, déplacé pour expliciter ce rôle. Son disque `GLF_ROOT`
et ses pilotes virtio ne décrivent pas les postes GLF-OS.

## Intégration prévue

Ajouter ce dépôt comme input verrouillé de la flake qui décrit le poste, puis
ajouter son module à la liste existante, en conservant tous les autres imports :

```nix
# Dans les modules de nixosConfigurations."GLF-OS" :
modules = [
  ./configuration.nix
  ./customized.nix
  glf.nixosModules.default
  glf-uki.nixosModules.secureBoot
];
```

`glf-uki` désigne l’input de ce dépôt, à déclarer dans la flake du poste. Pour ce
prototype, la configuration entière doit être évaluée avec NixOS unstable et une
révision prenant en charge `kmodigest` et `kernelPackages.rebuildImage`.
Le module ne remplace pas discrètement la base nixpkgs de la machine.

Après intégration, les sorties à construire sont celles du poste :

```sh
nix build /etc/nixos#nixosConfigurations.GLF-OS.config.system.build.glfKernel
nix build /etc/nixos#nixosConfigurations.GLF-OS.config.system.build.uki
```

Ces commandes construisent des artefacts non signés GLF. Importer le module ne
suffit pas à installer l’UKI sur l’ESP ni à l’intégrer au cycle de `glf-update`.
Ce raccordement doit construire, faire signer, vérifier puis installer l’UKI de
la même génération, avant de déclarer la mise à jour réussie.

## Signature et rôle de la CI

La CI peut préconstruire et mettre en cache des noyaux et modules pour des
configurations définies. Une UKI complète contient également des éléments
propres au poste : une UKI générique ne convient donc pas à toutes les machines.

Si l’UKI est assemblée sur le poste par le parcours `glf-update`, sa signature
avec la clé GLF exige un service de signature contrôlé par GLF. Ce service devra
authentifier et autoriser les demandes et vérifier les artefacts à signer : il ne
doit pas signer arbitrairement toute image reçue. La clé GLF reste côté GLF.
L’autre possibilité est de faire construire et signer chaque configuration
machine par une infrastructure centrale qui dispose de sa définition exacte.

Ce choix et son protocole restent à implémenter. La CI actuelle ne signe que les
artefacts de sa machine de test. Elle ne fournit pas encore une chaîne de mise à
jour signée utilisable par les postes.

## État de cette correction

Les fichiers de test sont distingués du module réutilisable et le module préserve
le noyau choisi par la machine. Aucun fichier de `/etc/nixos`, ni le programme
`glf-update` installé, n’a été modifié. Aucun rebuild ou déploiement du poste n’a
été lancé.

Le support distinct d’enrôlement de test avec shim Rocky et MokManager est
désormais disponible : voir [ENROLLMENT.md](ENROLLMENT.md). Il ne remplace pas
l’intégration de l’UKI au déploiement du poste.
