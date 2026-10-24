#!/usr/bin/env bash
set -euo pipefail
: "${GITHUB_REPOSITORY:?}"
tag=$(cat dist/release/tag.txt)
commit=$(jq -r .commit dist/release/release.json)
# Aucun --clobber : une publication existante ne doit jamais etre remplacee.
gh release create "$tag" --repo "$GITHUB_REPOSITORY" --target "$commit" \
  --title "Secure Boot $(jq -r .profile dist/release/release.json) $(jq -r .branch dist/release/release.json) ${commit:0:12}" \
  --notes 'Noyau et systemd-boot signes GLF, shim Rocky et MokManager inchanges. Initrd local non inclus. Utiliser release.json avec la meme revision NIX_SB.' \
  --draft --latest=false dist/release/glf-secureboot.tar.gz dist/release/release.json dist/release/build.json
# Promouvoir la release seulement une fois tous les assets televerses.
gh release edit "$tag" --repo "$GITHUB_REPOSITORY" --draft=false --latest
# Nettoyer uniquement apres la publication complete de la nouvelle version.
python3 "$(dirname "$0")/prune_releases.py" "$tag"
