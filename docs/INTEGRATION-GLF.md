# Intégration GLF-OS : shim → systemd-boot → UKI

Le projet expose un module NixOS opt-in (`nixosModules.default` ou `secureBoot`),
un overlay (`overlays.default`) et le paquet `glf-boot-tools`. L’import seul ne
change pas le démarrage ; `glf.boot.enable = true` active l’intégration.

## Passage par glf-apps

Le patch [integration/glf-os.patch](../integration/glf-os.patch) est préparé pour
le checkout GLF-OS consulté. Il ajoute cet input à `modules/glf-apps/flake.nix`,
compose son overlay avec celui des applications, réexporte son module et importe
ce dernier dans le module racine GLF-OS. Examiner puis appliquer dans GLF-OS :

```sh
git apply --check /chemin/NIX_SB/integration/glf-os.patch
git apply /chemin/NIX_SB/integration/glf-os.patch
```

La référence de développement est `configure-test-signing`, en attendant la fusion
sur `main`. Verrouiller le commit de l’input dans les locks utilisés par GLF-OS.
Le prototype exige **NixOS unstable**, notamment `kmodigest` et `rebuildImage` :
le simple ajout d’un input unstable ne transforme pas une configuration système
construite avec nixpkgs stable en configuration unstable.

Pour les dépôts d’applications importés avec `flake = false`, `default.nix`
permet aussi `pkgs.callPackage glf-boot-source { }` pour les outils ; le module
s’importe via `"${glf-boot-source}/nix/secure-boot.nix"`. L’overlay seul n’active
pas le chargeur.

## Configuration du poste

Conserver les imports existants de `/etc/nixos#GLF-OS`, notamment le matériel,
`configuration.nix`, `customized.nix` et `customConfig`. Ajouter l’activation dans
un module du poste ; voir [machine-example.nix](../integration/machine-example.nix).

```nix
glf.boot = {
  enable = true;
  signing.github = {
    repository = "Xdavius/NIX_SB";
    ref = "main";
    tokenFile = "/run/credentials/glf-github-token";
    allowPublicArtifacts = false;
  };
};
```

Le certificat public attendu est par défaut `GLF-TEST.pem`. Aucune clé privée de
signature n’est nécessaire sur le poste. Le jeton GitHub (droits de création de
releases brouillon, lancement de workflows et lecture des artefacts) doit être
fourni hors du store, dans un fichier accessible uniquement à root. Avec
`tokenFile = null`, les outils utilisent l’authentification `gh` du compte qui
installe le chargeur, généralement root. Un secret dans un fichier utilisateur
n’est pas automatiquement disponible à `sudo glf-update`.

Le dépôt actuel est public : les **artefacts signés**, contenant l’initrd, peuvent
être téléchargés. Utiliser un dépôt privé équipé du même workflow ou autoriser
explicitement `allowPublicArtifacts = true` pour une machine de test dont les
images peuvent être publiques. Les secrets d’initrd NixOS sont refusés par une
assertion ; cela ne détecte pas d’éventuels secrets ajoutés manuellement ailleurs.

## Cycle de glf-update

`glf-update` utilise `nixos-rebuild build` puis `nixos-rebuild boot`. L’intégration
remplace `system.build.installBootLoader`, donc aucun patch du script glf-update
n’est nécessaire. Lors de `boot` ou `switch` :

1. Lire `glf-boot.json` dans la génération exacte fournie par NixOS.
2. Assembler l’UKI avec son noyau enrichi, son initrd, ses paramètres et son `init`.
3. Soumettre les trois images (noyau, UKI, systemd-boot) dans une release brouillon
   GitHub portant un identifiant unique et un manifeste SHA-256.
4. Lancer `sign-request.yml` sur `main`, puis attendre l’approbation de
   `glf-signing`. Le responsable doit examiner la demande avant de l’approuver.
5. Vérifier localement les signatures et l’identité du contenu PE retourné,
   hors champs Authenticode, avant d’écrire les fichiers amorçables.
6. Installer une UKI propre à la génération et mettre à jour le défaut du menu.

La clé persistante reste dans GitHub Secrets. Le service n’exécute pas les images
soumises. Il vérifie le manifeste, ne signe que trois noms de fichiers fixes et
retourne des artefacts. Les demandes brouillon sont conservées pour audit et
peuvent être supprimées manuellement après usage ; elles ne sont jamais publiées
automatiquement. L’échec ou le refus de signature fait échouer l’installation.
Les fichiers de démarrage précédents restent alors inchangés.

## Fichiers installés

```text
EFI/GLF/shimx64.efi              shim Rocky signé par Microsoft
EFI/GLF/mmx64.efi                MokManager Rocky
EFI/GLF/grubx64.efi              systemd-boot signé GLF (ce n’est pas GRUB)
EFI/BOOT/BOOTX64.EFI             shim, chemin UEFI de secours
EFI/BOOT/mmx64.efi               MokManager
EFI/BOOT/grubx64.efi             systemd-boot signé GLF
EFI/systemd/systemd-bootx64.efi  copie signée au chemin standard
EFI/Linux/glf-<generation>.efi  UKI signée propre à la génération
loader/loader.conf              défaut, délai, éditeur désactivé
```

Le nom `grubx64.efi` satisfait le chemin de second étage attendu par le shim Rocky.
Le binaire installé à ce nom est **systemd-boot**, à la différence du support
séparé d’enrôlement où c’est MokManager. systemd-boot utilise le protocole shim
pour vérifier les images signées avec MOK.

L’installateur ne lance pas `bootctl install`, qui remplacerait le shim de secours.
Le service automatique de mise à jour systemd-boot est désactivé pour éviter le
remplacement du chargeur signé par un binaire non signé. Si
`boot.loader.efi.canTouchEfiVariables` est vrai, l’installateur crée une entrée
UEFI `GLF-OS shim` si ce chemin n’existe pas, et fixe le défaut systemd-boot.

## Générations et limites

Les anciennes UKI sont conservées pour le retour arrière. Réinstaller une ancienne
génération compatible remet son entrée par défaut après signature ; les anciens
systèmes sans `glf-boot.json` ne sont pas convertis automatiquement. La purge des
UKI anciennes reste manuelle : surveiller l’espace libre de l’ESP et conserver les
générations NixOS correspondantes pour éviter que leur closure soit collectée.

Cette première intégration prend en charge x86_64, une seule ESP FAT montée,
sans XBOOTLDR ni spécialisations. Elle ne déploie pas automatiquement sur le poste
de développement. La signature nécessite Internet, un jeton GitHub et une
approbation ; ce n’est pas une mise à jour hors ligne.

Le workflow de signature doit d’abord être fusionné sur la branche protégée
`main`. Tant que la PR n’est pas fusionnée, le parcours distant ne peut pas être
activé en conditions réelles. Les tests locaux emploient un signataire de test
jetable pour vérifier les signatures et l’installation, sans extraire la clé GLF.

## Catalogue de drivers approuvés

Le module installe les deux drivers de `pkgs/repo/default.nix` et injecte
exclusivement leurs certificats et ceux du noyau natif. Retirer les anciennes
déclarations de ces drivers dans `boot.extraModulePackages` lorsqu’elles
proviennent d’autres définitions/overlays : elles ne doivent pas faire doublon.
Les autres modules externes (Wi-Fi, NVIDIA, VirtualBox, etc.) doivent être ajoutés
au catalogue et revus avant usage avec cette politique.

Le signataire accepte uniquement le noyau et le chargeur du dépôt protégé :
aligner la révision nixpkgs du poste sur le `flake.lock` approuvé. Changer le noyau,
un driver ou son compilateur peut produire une autre image qui sera refusée.
Le matériel, l’initrd, les systèmes de fichiers et les applications restent propres
au poste. Voir [pkgs/repo/README.md](../pkgs/repo/README.md).
