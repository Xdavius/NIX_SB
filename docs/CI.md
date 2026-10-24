# CI par branche et par canal GLF-OS

Chaque branche de version (Rising actuellement) est traitée avec deux profils :

| Profil | Dépôt channels | Sorties internes NIX_SB |
| --- | --- | --- |
| `current` | `glf-os-channels` | `kernel`, `ci`, `checks.…packages` |
| `testing` | `testing-channels` | `testing-kernel`, `testing-ci`, `checks.…testing-packages` |

Chaque dépôt channels fournit son propre couple `nixpkgs` / `nixpkgs-unstable`.
Le socle noyau est le `nixpkgs` du profil. **Testing n’est pas l’entrée unstable
du canal current.** Les deux sources et leurs pins sont enregistrés séparément
dans un `flake.lock` temporaire ; aucun rafraîchissement implicite n’a lieu pendant un build.

Exception temporaire autorisée : `secureboot-release.yml` n’exécute que le parcours testing
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
`secureboot-PROFIL-HASH_BRANCHE-COMMIT-HASH_CHANNELS`. Le descripteur release.json contient
`profile`, `branch`, `commit`, `url`, `archiveHash` et `hash`. Le manifeste build.json trace le
dépôt channels, son commit et les pins nixpkgs/unstable. La release reste draft
jusqu’à la fin des uploads. Aucun remplacement automatique d’une release existante.
Lors de sa publication, la CI marque explicitement la release « Latest » afin
que `glf-update` découvre la nouvelle version. Ce statut est global au dépôt ;
actuellement, seul le profil testing est publié.
Les artefacts Actions expirent après sept jours.

Apres chaque publication reussie, `ci/prune_releases.py` conserve au maximum
**7 releases Secure Boot publiees au total**, tous profils et branches confondus.
Le tri utilise la date de publication, puis l'identifiant GitHub ; la release du
run est toujours conservee. Les releases excedentaires, leurs assets et leurs
tags sont supprimes. Les brouillons et les releases dont le tag ne correspond
pas au format Secure Boot restent intacts. Une erreur API interrompt le nettoyage.
Le job de publication est serialise entre branches et profils pour eviter des
nettoyages concurrents. Aucun nettoyage n'est lance si la publication echoue.

Un ancien descripteur peut donc devenir inutilisable pour un nouveau telechargement.
Les fichiers deja installes sur les postes ne sont pas supprimes par ce nettoyage.

## Channels mouvants, sans lock versionne

Le workflow `secureboot-release.yml` tourne chaque jour a **05:23 UTC** (06:23 en hiver,
07:23 en ete a Paris), sur push, sur PR et sur lancement manuel. Le cron devient
actif apres fusion sur la branche par defaut ; GitHub peut retarder son execution.

NIX_SB ne versionne plus `flake.lock`. Les branches `main` des deux channels GLF
sont les autorites sur les versions. Le job `resolve` genere un lock temporaire,
verifie les liens `follows` et transmet exactement ce lock aux jobs de validation,
construction et signature. Les commandes utilisent `path:$PWD` afin que Nix
inclue ce fichier ignore par Git. Aucun rafraichissement entre ces etapes.

L'identite d'une release comprend profil, branche, commit NIX_SB et empreinte des
revisions du channel et de ses deux nixpkgs. Si cette release publique existe deja,
les controles sont executes mais le build, la signature et la publication sont
omis. Une erreur de l'API GitHub fait echouer le controle. Un changement du channel
peut donc produire une nouvelle release au meme commit NIX_SB, sans PR ni commit
automatique. Les definitions locales des pilotes restent maintenues dans le depot.

Le lock utilise est conserve dans l'archive signee ; `build.json` trace les
revisions. Pour reproduire une release, utiliser son commit NIX_SB et extraire
son `flake.lock` a la racine avant d'executer les commandes avec `path:$PWD`.
GLF-OS doit utiliser les memes revisions de channels pour consommer cette release.
La surveillance ne modifie aucun fichier GLF-OS.

Current est toujours explicitement indisponible. Son channel est resolu et trace
dans le lock temporaire, mais seule une modification du profil testing declenche
une publication testing. Reactiver current exige une validation de compatibilite
et une modification explicite du workflow.

Pour resoudre les channels manuellement puis lancer les controles :

```sh
nix flake update --flake "path:$PWD" --refresh
python3 ci/channels.py --profile current
python3 ci/channels.py --profile testing
GLF_CHANNEL=testing nix develop "path:$PWD#testing-ci" --no-update-lock-file --command bash ci/check.sh
```

`--glfos-lock /chemin/flake.lock` permet de comparer les revisions resolues a
celles du checkout GLF-OS correspondant. Les commandes sans rafraichissement
reutilisent le lock local ignore ; relancer la commande update pour suivre les
nouveautes des channels.
