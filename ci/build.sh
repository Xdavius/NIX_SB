#!/usr/bin/env bash
set -euo pipefail
test -f flake.lock
mkdir -p dist/unsigned
nix build --no-update-lock-file .#kernel .#uki .#certificates --out-link result
kernel=$(readlink -f result)
uki=$(readlink -f result-1)
certs=$(readlink -f result-2)
cp "$kernel/bzImage" dist/unsigned/kernel.efi
cp "$uki/glf-os_prototype.efi" dist/unsigned/glf-os.efi
cp "$certs/modules.cer" "$certs/bundle.sha256" dist/unsigned/
# Le manifeste est la simulation Attic des closures Nix construites.
nix path-info --recursive --json "$kernel" "$uki" "$certs" > dist/unsigned/nix-closure.json
printf '%s\n' "$kernel" "$uki" "$certs" > dist/unsigned/store-paths.txt
(cd dist/unsigned && sha256sum kernel.efi glf-os.efi modules.cer bundle.sha256 > SHA256SUMS)
