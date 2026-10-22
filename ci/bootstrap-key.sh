#!/usr/bin/env bash
# Bootstrap unique dans un job protege, jamais dans un build Nix.
set +x
set -euo pipefail
umask 077
[[ ${GITHUB_ACTIONS:-} == true ]] || { echo 'Bootstrap reserve a la CI.' >&2; exit 1; }
: "${GH_TOKEN:?Jeton autorisant les secrets et variables environnement requis}"
: "${GITHUB_REPOSITORY:?Depot absent}"
existing=$(gh secret list --repo "$GITHUB_REPOSITORY" --env glf-signing --json name --jq '.[].name')
if [[ $existing == *GLF_SIGNING_KEY_PEM* || $existing == *GLF_SIGNING_CERT_PEM* ]]; then
  echo 'Cle ou certificat deja presents : aucune regeneration autorisee.' >&2
  exit 1
fi
work=$(mktemp -d)
trap 'rm -rf -- "$work"' EXIT
openssl req -newkey rsa:3072 -nodes -x509 -sha256 -days 3650 \
  -subj '/CN=GLF-OS Secure Boot/' -keyout "$work/key.pem" -out "$work/cert.pem" 2>/dev/null
# La cle est ecrite en premier : toute interruption suivante bloque un nouveau bootstrap.
gh secret set GLF_SIGNING_KEY_PEM --repo "$GITHUB_REPOSITORY" --env glf-signing < "$work/key.pem"
gh secret set GLF_SIGNING_CERT_PEM --repo "$GITHUB_REPOSITORY" --env glf-signing < "$work/cert.pem"
fingerprint=$(openssl x509 -in "$work/cert.pem" -noout -fingerprint -sha256)
gh variable set GLF_CERT_SHA256 --repo "$GITHUB_REPOSITORY" --env glf-signing --body "${fingerprint#*=}"
mkdir -p dist/public
cp "$work/cert.pem" dist/public/GLF.pem
openssl x509 -in "$work/cert.pem" -outform DER -out dist/public/GLF.cer
openssl x509 -in "$work/cert.pem" -noout -subject -dates -fingerprint -sha256 > dist/public/GLF.txt
