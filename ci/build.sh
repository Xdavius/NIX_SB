#!/usr/bin/env bash
set -euo pipefail
test -f flake.lock
mkdir -p dist/unsigned
nix build --no-update-lock-file .#kernel .#uki .#certificates .#systemd-boot --out-link result
kernel=$(readlink -f result)
uki=$(readlink -f result-1)
certs=$(readlink -f result-2)
sdboot=$(readlink -f result-3)
cp "$sdboot/systemd-bootx64.efi" dist/unsigned/
cp "$kernel/bzImage" dist/unsigned/kernel.efi
cp "$uki/glf-os_prototype.efi" dist/unsigned/glf-os.efi
cp "$certs/modules.cer" "$certs/bundle.sha256" dist/unsigned/
cp "$certs/approved-modules.json" dist/unsigned/
# Le manifeste est la simulation Attic des closures Nix construites.
nix path-info --recursive --json "$kernel" "$uki" "$certs" "$sdboot" > dist/unsigned/nix-closure.json
printf '%s\n' "$kernel" "$uki" "$certs" "$sdboot" > dist/unsigned/store-paths.txt
(cd dist/unsigned && sha256sum kernel.efi glf-os.efi systemd-bootx64.efi modules.cer bundle.sha256 approved-modules.json > SHA256SUMS)
