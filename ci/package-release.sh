#!/usr/bin/env bash
# Prepare les artefacts publics et leur descripteur Nix, sans aucun secret.
set -euo pipefail
: "${GITHUB_REPOSITORY:?}"
(cd dist/signed && sha256sum --check SHA256SUMS)
commit=$(jq -r .commit dist/signed/release.json)
branch=$(jq -r .branch dist/signed/release.json)
profile=$(jq -r .profile dist/signed/release.json)
variant=$(jq -r '.kernelVariant // "default"' dist/signed/release.json)
[[ $profile == current || $profile == testing ]] || exit 1
[[ $commit =~ ^[a-f0-9]{40}$ ]] || exit 1
# Les channels peuvent changer sans nouveau commit NIX_SB.
tag=$(python3 "$(dirname "$0")/release_tag.py" dist/signed/release.json)
mkdir -p dist/release
cp dist/signed/release.json dist/release/build-"$variant".json
hash=$(nix hash path dist/signed)
tar --sort=name --mtime=@0 --owner=0 --group=0 --numeric-owner \
  -C dist/signed -czf dist/release/glf-secureboot-"$variant".tar.gz .
archive_hash=$(nix hash file dist/release/glf-secureboot-"$variant".tar.gz)
jq -n --arg url "https://github.com/$GITHUB_REPOSITORY/releases/download/$tag/glf-secureboot-$variant.tar.gz" \
  --arg kernelVariant "$variant" --arg archiveHash "$archive_hash" --arg profile "$profile" --arg hash "$hash" --arg commit "$commit" --arg branch "$branch" \
  '{version:2,kernelVariant:$kernelVariant,archiveHash:$archiveHash,profile:$profile,url:$url,hash:$hash,commit:$commit,branch:$branch}' > dist/release/release-"$variant".json
printf '%s\n' "$tag" > dist/release/tag.txt
