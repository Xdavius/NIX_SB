> Intégration native : voir [MIGRATION-GLF.md](MIGRATION-GLF.md).
> La source du build signé est désormais `ci/approved-source.json` ; les exemples
> d’import du prototype séparé ci-dessous sont historiques.

# Signature GitHub sans clé privée sur le poste

Le workflow `.github/workflows/sign-request.yml` signe des demandes provenant de
machines GLF-OS. Il doit être fusionné sur `main` avant utilisation. Il utilise
les secrets de test déjà présents dans `glf-signing`, la protection de `main`,
la variable `GLF_SIGNING_ENABLED` et l’approbation manuelle existante.

## Demande et validation

`glf-github-sign` crée une release **brouillon** `glf-sign-<UUID>` et y dépose
`kernel.efi`, `glf-os.efi`, `systemd-bootx64.efi` et `request.json`. Le manifeste
contient le chemin de génération et les empreintes des trois images. Sa propre
empreinte est transmise séparément à `workflow_dispatch`.

Le responsable examine la demande brouillon avant d’approuver l’environnement
`glf-signing`. Cette approbation est une autorisation de signer ces images, pas
une simple formalité : le noyau, le chargeur et le stub sont contrôlés contre le
dépôt approuvé, mais le contenu de l’initrd et la configuration du poste restent
à examiner. Seuls les collaborateurs autorisés à
créer des releases et lancer les workflows peuvent soumettre une demande.

Le job de signature télécharge uniquement les quatre fichiers attendus, vérifie
le manifeste et le format PE x86_64. Il construit le noyau et systemd-boot depuis
le checkout protégé et exige leur identité avec les images soumises. Il extrait
les sections de données de l’UKI, impose `module.sig_enforce=1` et
`lockdown=integrity`, reconstruit l’UKI avec le stub approuvé et compare le résultat.
Un stub modifié, un autre noyau embarqué ou une section supplémentaire sont refusés.
Le bundle de confiance vient uniquement des modules natifs et de `pkgs/repo`.
Le job rend ensuite la clé disponible exclusivement
à l’étape de signature. Il ne décompresse ni n’exécute le contenu des images.
Il publie les images signées et le manifeste comme artefact pendant sept jours.

Le client retrouve son run par UUID, attend sa réussite et télécharge l’artefact.
Il vérifie la signature contre le certificat public configuré et compare les
fichiers PE avant/après en excluant seulement les champs modifiés par la signature
Authenticode et l’alignement final nul. Une image différente, même signée avec
la bonne clé, est refusée.

## Accès du poste

Fournir à root une authentification `gh` ou un fichier de jeton hors du store
via `glf-securebootUKI.signing.github.tokenFile`. Le jeton doit pouvoir créer une release
brouillon, envoyer ses assets, lancer le workflow et lire ses runs/artefacts.
Ne jamais écrire le jeton dans un fichier Nix ou le committer.

Le dépôt `Xdavius/NIX_SB` est public : les artefacts signés peuvent exposer
l’initrd et les informations du poste. Le client refuse par défaut cette
publication ; une machine de test doit explicitement fixer
`allowPublicArtifacts = true`. Un dépôt privé peut héberger le même workflow
avec ses propres secrets et protections.

L’attente maximale est configurable. En cas de refus, timeout ou erreur de
signature, l’installateur ne modifie pas les fichiers amorçables de l’ESP. Les
releases brouillon restent disponibles pour diagnostic/audit et sont à nettoyer
manuellement. Aucune publication de release ou suppression de demande n’est
faite automatiquement.

## Tests et limites

Les tests automatisés utilisent une clé jetable pour vérifier les signatures,
la correspondance du contenu, les générations et l’échec sans modification de
l’ESP. Ils ne récupèrent pas la clé persistante de GitHub.

Le service impose une revue humaine et un accès réseau à chaque installation.
Il ne constitue pas une infrastructure de signature de production ni un service
anonyme pour tous les utilisateurs GLF-OS. Une généralisation demandera une
politique d’autorisation, une validation des builds et une gestion des quotas.
