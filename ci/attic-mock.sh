#!/usr/bin/env bash
set -euo pipefail
# Simulation stricte : aucun client Attic, token ou acces reseau.
test -s dist/signed/GLF.cer
(cd dist/signed && sha256sum --check SHA256SUMS)
jq -n --arg commit "${GITHUB_SHA:-local}" \
  --rawfile paths dist/signed/store-paths.txt \
  --rawfile hashes dist/signed/SHA256SUMS \
  '{mode:"mock", uploaded:false, commit:$commit, unsignedStorePaths:($paths|split("\n")|map(select(length>0))), signedArtifacts:$hashes,
    note:"Les fichiers signes doivent etre importes dans le store avant une publication Attic reelle."}' \
  > dist/attic-mock.json
echo 'Attic simule : manifeste cree, aucun envoi effectue.'
