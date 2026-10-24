# Signature centralisée des composants GLF

Le workflow `.github/workflows/secureboot-release.yml` surveille les channels GLF
et construit et publie les composants Secure Boot **sans UKI**. Le workflow de demandes
`sign-request.yml` et le client `glf-secureboot-sign` sont retirés.

1. `validate` effectue les contrôles et tests locaux avec clé jetable.
2. `build` construit noyau enrichi, certificats, systemd-boot et shim Rocky.
3. `sign` vérifie les empreintes puis signe uniquement `kernel.efi` et
   `systemd-bootx64.efi` avec les secrets de `glf-signing-production`.
4. `publish` publie l’archive et son descripteur Nix dans une release identifiée par le commit et les révisions du channel,
   avec `contents: write`, mais sans accès à la clé privée.

Shim Rocky et MokManager sont copiés sans modification. Le certificat public
GLF est livré au format PEM et DER. Le consommateur utilise le certificat
épinglé dans NIX_SB, jamais une confiance déduite de la seule réponse téléchargée.

Le job `sign` exige une branche protégée et `GLF_SIGNING_ENABLED=true` ;
l’environnement autorise actuellement Rising, sans approbation manuelle pour
chaque publication. Une nouvelle branche doit y être explicitement autorisée.
La clé existante est commune aux versions ; ne pas relancer le bootstrap.

La clé de production a été créée par le run
[39764263507](https://github.com/Xdavius/NIX_SB/actions/runs/39764263507).
Le bootstrap reste désactivé (`GLF_KEY_BOOTSTRAP_ENABLED=false`) et son
approbation distincte reste obligatoire. Son jeton temporaire a été retiré.
Les secrets de test historiques ne sont pas utilisés pour publier.

Le test de signature par poste
[39766464511](https://github.com/Xdavius/NIX_SB/actions/runs/39766464511)
avait réussi avec des images fictives ; il constitue une preuve historique de
fonctionnement de la clé, pas une validation de la nouvelle publication.

Aucun initrd utilisateur ni jeton GitHub n’est nécessaire sur les postes.
L’initrd et les paramètres restent locaux et non authentifiés par Secure Boot.
Les modules doivent être approuvés par le noyau enrichi, indépendamment de la
signature EFI du noyau.

Le contrat complet et les exemples Nix sont dans
[integration-glfos.md](../integration-glfos.md).
