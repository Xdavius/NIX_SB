#!/usr/bin/env bash
set -euo pipefail
: "${GITHUB_REPOSITORY:?}"
# Refuser la publication si une archive manque ou si les pins different.
tag=$(python3 -m ci.release_bundle dist/release)
commit=$(jq -r .commit dist/release/release-default.json)
# Aucun --clobber : une publication existante ne doit jamais etre remplacee.
gh release create "$tag" --repo "$GITHUB_REPOSITORY" --target "$commit" \
  --title "Secure Boot $(jq -r .profile dist/release/release-default.json) $(jq -r .branch dist/release/release-default.json) ${commit:0:12}" \
  --notes 'Deux noyaux signes GLF : default et latest. Chaque archive contient ses composants Secure Boot et son manifeste. Utiliser release-default.json ou release-latest.json avec la meme revision NIX_SB. Initrd local non inclus.' \
  --draft --latest=false \
  dist/release/glf-secureboot-default.tar.gz dist/release/release-default.json dist/release/build-default.json \
  dist/release/glf-secureboot-latest.tar.gz dist/release/release-latest.json dist/release/build-latest.json
# Promouvoir seulement apres verification et upload des deux variantes.
gh release edit "$tag" --repo "$GITHUB_REPOSITORY" --draft=false --latest
python3 "$(dirname "$0")/prune_releases.py" "$tag"
