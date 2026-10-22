# CI par branche et par canal GLF-OS

Chaque branche de version (Rising actuellement) est traitée avec deux profils :

| Profil | Dépôt channels | Sorties internes NIX_SB |
| --- | --- | --- |
| `current` | `glf-os-channels` | `kernel`, `ci`, `checks.…packages` |
| `testing` | `testing-channels` | `testing-kernel`, `testing-ci`, `checks.…testing-packages` |

Chaque dépôt channels fournit son propre couple `nixpkgs` / `nixpkgs-unstable`.
Le socle noyau est le `nixpkgs` du profil. **Testing n’est pas l’entrée unstable
du canal current.** Les deux sources et leurs pins sont enregistrés séparément
dans `flake.lock` ; aucun rafraîchissement implicite n’a lieu pendant un build.

Exception temporaire autorisée : `uki.yml` n’exécute que le parcours testing
via `channel.yml`. Le job `current-unavailable` affiche explicitement un
avertissement et un résumé ; il ne prétend pas valider current. Aucun build,
signature ou publication current n’est lancé.

Le statut obligatoire `validate` exige la réussite de testing. Un échec ou une
annulation testing bloque toujours la fusion. Les PR ne construisent pas de noyau
et ne signent ni ne publient. Pour réactiver current, résoudre sa compatibilité
puis restaurer son parcours et son contrôle obligatoire dans le workflow.

La signature exige une branche protégée autorisée dans l’environnement
`glf-signing-production` et `GLF_SIGNING_ENABLED=true`. Cette restriction vaut
pour les deux profils. Le job de publication a contents:write sans clé privée.
Le shim Rocky est conservé intact ; seuls noyau et systemd-boot sont signés GLF.

Les artefacts et releases portent le profil pour empêcher leur mélange :
`secureboot-PROFIL-HASH_BRANCHE-COMMIT`. Le descripteur release.json contient
`profile`, `branch`, `commit`, `url`, `archiveHash` et `hash`. Le manifeste build.json trace le
dépôt channels, son commit et les pins nixpkgs/unstable. La release reste draft
jusqu’à la fin des uploads. Aucun remplacement automatique d’une release existante.
Les artefacts Actions expirent après sept jours, pas les assets de release.

## Actualisation contrôlée des pins

```sh
nix flake update glf-channels testing-channels
python3 ci/channels.py --profile current
python3 ci/channels.py --profile testing
```

Les sources peuvent indiquer une branche mouvante : le lock NIX_SB enregistre
le commit résolu. Conserver les mêmes pins dans les locks de consommation GLF-OS.
`--glfos-lock /chemin/flake.lock` compare le profil sélectionné avec le couple
résolu sous glf-channels du lock GLF-OS fourni (utiliser le checkout correspondant).
La CI n’a pas besoin de modifier ou de cloner GLF-OS.

Contrôles séparés :

```sh
GLF_CHANNEL=current nix develop .#ci --command bash ci/check.sh
GLF_CHANNEL=testing nix develop .#testing-ci --command bash ci/check.sh
```

## État des pins vérifiés

- current : channels `dc9d3bd`, nixpkgs `26f4107`, unstable `55bfb4d`.
  Ces deux pins nixpkgs proposent 6.18.56 sans rebuildImage ; l’évaluation du
  noyau enrichi échoue explicitement et sa publication reste bloquée.
- testing : channels `dbb24ff`, nixpkgs résolu `02c087f`, unstable `9fbb54b`.
  Le socle testing fournit 6.18.57 avec rebuildImage ; son contrat de paquets
  s’évalue correctement.

Le canal actuel nécessite toujours une mise à jour compatible ou un rétroportage
validé. Aucun repli silencieux sur testing. Aucune publication distante de cette
nouvelle chaîne n’a encore été exécutée.
