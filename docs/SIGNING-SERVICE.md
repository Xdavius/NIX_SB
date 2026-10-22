# Signature gérée dans NIX_SB

`boot-tools` fournit `glf-secureboot-sign`, client du workflow GitHub de ce dépôt. L’installateur
`glf-secureboot-install --config CONFIG GENERATION` assemble les images puis appelle
la liste d’arguments `signerCommand` sans shell :

```text
COMMANDE [ARGUMENTS] --certificate CERT --system GENERATION DOSSIER_ENTREE DOSSIER_SORTIE
```

La commande doit rendre `kernel.efi`, `glf-os.efi` et `systemd-bootx64.efi` signés
dans le dossier de sortie. Elle échoue avec un code non nul en cas de refus.
Le client utilise une draft release, déclenche `sign-request.yml`, attend le résultat
et vérifie les images signées. La clé privée ne passe jamais par une dérivation Nix.

Configuration runtime de l’installateur :

```json
{
  "esp": "/boot",
  "certificate": "/etc/secureboot/GLF.pem",
  "shim": "/nix/store/…-rocky-shim-signed/share/efi",
  "signerCommand": ["/nix/store/…-glf-secureboot/bin/glf-secureboot-sign", "--repo", "Xdavius/NIX_SB", "--ref", "Rising", "--token-file", "/run/secrets/github-token", "--timeout", "28800"],
  "timeout": "5",
  "canTouchEfiVariables": false
}
```

`timeout` est le délai du menu systemd-boot, pas celui du signataire.
Le champ historique `githubSigner` n’est plus accepté.

La génération doit contenir `init`, `etc/os-release` et `glf-secureboot.json` :

```json
{
  "version": 1,
  "kernel": "/nix/store/…/bzImage",
  "initrd": "/nix/store/…/initrd",
  "stub": "/nix/store/…/linuxx64.efi.stub",
  "systemdBoot": "/nix/store/…/systemd-bootx64.efi",
  "ukify": "/nix/store/…/lib/systemd/ukify",
  "kernelVersion": "VERSION_MODULES",
  "kernelParams": ["root=LABEL=ROOT", "module.sig_enforce=1", "lockdown=integrity"]
}
```

Le consommateur fournit les chemins exacts et les paramètres matériels.
L’installateur ajoute `init=GENERATION/init`, vérifie les signatures et compare
le contenu PE retourné avant de copier les images dans l’ESP. Il conserve les
anciennes UKI. Les tests utilisent une clé éphémère et un répertoire temporaire.

## Service de ce dépôt

`sign-request.yml` accepte les branches de version protégées avec `GLF_SIGNING_ENABLED=true`
(variable du dépôt). Le premier job construit les composants du commit NIX_SB
exécuté et vérifie noyau, chargeur, paramètres obligatoires et stub de l’UKI.
Le second job, dans l’environnement protégé `glf-signing`, signe les fichiers
validés avec les secrets `GLF_SIGNING_KEY_PEM` et `GLF_SIGNING_CERT_PEM`, et la
variable d’empreinte `GLF_CERT_SHA256`. Il publie uniquement les images signées,
le certificat public et le manifeste. Les secrets ne sont pas accessibles au
job de build. Le consommateur doit utiliser le même nixpkgs, noyau et catalogue.

Configurer `glf-signing` avec approbateurs et accès limité aux branches de version protégées.
Le client nécessite un jeton capable de créer des draft releases, déclencher
les workflows et télécharger leurs artefacts. Les postes ne reçoivent jamais
le jeton d’administration des secrets ni la clé de signature.
Sur un dépôt public, les artefacts peuvent exposer l’initrd du poste : le client
refuse ce parcours sauf option explicite `--allow-public-artifacts`. Aucun
secret d’initrd ne doit être envoyé. Les drafts sont conservées pour audit.

## Création unique de la clé

Le workflow manuel `bootstrap-key.yml` est également limité aux branches protégées.
Créer au préalable les environnements `glf-signing` et `glf-key-bootstrap`, avec
approbation obligatoire et restriction aux branches de version approuvées. Dans `glf-key-bootstrap`,
fournir `GLF_KEY_ADMIN_TOKEN`, jeton limité à ce dépôt autorisant la lecture et
l’écriture des secrets et variables d’environnement. `GITHUB_TOKEN` ne suffit pas.
Activer temporairement la variable de dépôt `GLF_KEY_BOOTSTRAP_ENABLED=true`.

Le job génère une clé RSA 3072 et son certificat, écrit la clé et le certificat
dans les secrets de `glf-signing`, puis l’empreinte dans sa variable. Il publie
seulement `GLF.pem`, `GLF.cer` et les informations publiques. Il refuse de démarrer
si l’un des deux secrets existe déjà, y compris la clé de test historique :
aucun remplacement ou passage automatique de la clé de test en production.

Après bootstrap, conserver le certificat public, vérifier son empreinte,
désactiver `GLF_KEY_BOOTSTRAP_ENABLED` et retirer le jeton d’administration.
En cas d’échec après écriture de la clé, ne pas supprimer celle-ci pour relancer :
le blocage est volontaire et demande une récupération contrôlée. Le workflow
ne fournit pas une rotation de clé ni une garantie matérielle de non-exportabilité.
Les administrateurs et jobs autorisés peuvent techniquement accéder aux secrets.

Aucun workflow n’a été déclenché, aucun secret créé par cette modification.
Les tests locaux du client simulent GitHub sans réseau ; le parcours réel reste
à valider après configuration des protections et déploiement des workflows.

## Branches de version GLF-OS

`Rising` est la première branche de version. Le client exige `--ref Rising`
(ou le nom exact d’une autre version) ; aucun repli implicite vers main.
La signature reconstruit les composants depuis le commit de la branche ciblée.
Protéger chaque branche de version et autoriser celle-ci dans les environnements
GitHub avant d’activer sa signature. Une branche non protégée peut être construite,
mais ne peut pas utiliser le workflow de signature.
La clé GLF est commune aux versions et n’est pas régénérée pour une nouvelle branche.
Les workflows workflow_dispatch doivent aussi exister sur la branche par défaut
GitHub pour être déclenchables ; `--ref` choisit ensuite la branche exécutée.
