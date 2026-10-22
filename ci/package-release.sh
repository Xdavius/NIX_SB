#!/usr/bin/env bash
# Prepare les artefacts publics et leur descripteur Nix, sans aucun secret.
set -euo pipefail
: "${GITHUB_REPOSITORY:?}"
(cd dist/signed && sha256sum --check SHA256SUMS)
commit=$(jq -r .commit dist/signed/release.json)
branch=$(jq -r .branch dist/signed/release.json)
profile=$(jq -r .profile dist/signed/release.json)
[[ $profile == current || $profile == testing ]] || exit 1
[[ $commit =~ ^[a-f0-9]{40}$ ]] || exit 1
# Le SHA identifie le contenu ; le hash du nom de branche evite les collisions.
branch_hash=$(printf '%s' "$branch" | sha256sum | cut -c1-12)
tag="secureboot-${profile}-${branch_hash}-${commit}"
mkdir -p dist/release
cp dist/signed/release.json dist/release/build.json
hash=$(nix hash path dist/signed)
tar --sort=name --mtime=@0 --owner=0 --group=0 --numeric-owner \
  -C dist/signed -czf dist/release/glf-secureboot.tar.gz .
jq -n --arg url "https://github.com/$GITHUB_REPOSITORY/releases/download/$tag/glf-secureboot.tar.gz" \
  --arg profile "$profile" --arg hash "$hash" --arg commit "$commit" --arg branch "$branch" \
  '{version:1,profile:$profile,url:$url,hash:$hash,commit:$commit,branch:$branch}' > dist/release/release.json
printf '%s\n' "$tag" > dist/release/tag.txt
