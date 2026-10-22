# Certificat GLF-OS Secure Boot de production

Créé par le workflow protégé :
https://github.com/Xdavius/NIX_SB/actions/runs/39764263507

- Sujet : CN=GLF-OS Secure Boot
- Validité : 22 octobre 2026 au 19 octobre 2036 (UTC).
- SHA256 du certificat :
  `63:3F:DE:4E:91:1D:10:02:BB:D5:8B:39:45:D0:2B:C4:3F:1B:84:0E:6F:0D:5C:95:3B:57:3E:77:A6:56:BF:BF`

`GLF.pem` sert à vérifier les images signées. `GLF.cer` est le même certificat
au format DER, destiné à l’enrôlement MOK. Le consommateur doit épingler ce
certificat depuis une révision approuvée du dépôt, pas le choisir dans une réponse
de signature. L’enrôlement sur une machine reste une opération distincte.

La clé privée a été créée dans le job GitHub et enregistrée uniquement dans le
secret GLF_SIGNING_KEY_PEM de l’environnement glf-signing-production. Elle n’a
pas été téléchargée ni incluse dans ces fichiers. Les secrets de test restent
dans l’environnement historique glf-signing.
