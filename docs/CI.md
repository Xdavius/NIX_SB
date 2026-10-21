# CI active dans GLF-OS

Le service est déplacé dans le dépôt officiel `xdavius/glf-os`, branche dédiée
`feature/secureboot-uki`. `develop` reste liée au projet mère.

La procédure actuelle est dans
[secureboot/docs/CI.md](https://framagit.org/xdavius/glf-os/-/blob/feature/secureboot-uki/secureboot/docs/CI.md).
Elle couvre le runner isolé, les protections GitLab, la génération unique de la
clé de production et l'approbation manuelle des signatures.

Les jobs GitHub de signature sont retirés et la variable
`GLF_SIGNING_ENABLED` vaut `false`. Les anciens secrets de test ne sont ni supprimés ni utilisés
pour la production. Aucune clé de production n'a été générée localement.

Les jobs GitHub restants vérifient le banc de tests historique. Pour le déploiement,
utiliser exclusivement la CI et le module natifs du dépôt GLF-OS.
