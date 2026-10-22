#!/usr/bin/env bash
set -euo pipefail
flake_ref=${GLF_FLAKE_REF:-.}
mkdir -p dist/unsigned
nix build --no-update-lock-file "$flake_ref#kernel" "$flake_ref#uki" "$flake_ref#certificates" "$flake_ref#systemd-boot" --out-link result
kernel=$(readlink -f result)
uki=$(readlink -f result-1)
certs=$(readlink -f result-2)
sdboot=$(readlink -f result-3)
cp --remove-destination "$sdboot/systemd-bootx64.efi" dist/unsigned/
cp --remove-destination "$kernel/bzImage" dist/unsigned/kernel.efi
cp --remove-destination "$uki/glf-os_prototype.efi" dist/unsigned/glf-os.efi
cp --remove-destination "$certs/modules.cer" "$certs/bundle.sha256" dist/unsigned/
cp --remove-destination "$certs/approved-modules.json" dist/unsigned/
# Le manifeste est la simulation Attic des closures Nix construites.
nix path-info --recursive --json --json-format 1 "$kernel" "$uki" "$certs" "$sdboot" > dist/unsigned/nix-closure.json
printf '%s\n' "$kernel" "$uki" "$certs" "$sdboot" > dist/unsigned/store-paths.txt
export GLF_RELEASE_BRANCH="${GITHUB_REF_NAME:-$(git branch --show-current)}"
export GLF_RELEASE_COMMIT="${GITHUB_SHA:-$(git rev-parse HEAD)}"
python3 - <<'PYMETA'
import json
import os
from pathlib import Path
metadata = {
    "branch": os.environ["GLF_RELEASE_BRANCH"],
    "commit": os.environ["GLF_RELEASE_COMMIT"],
    "kernel": json.loads(Path("kernel.json").read_text())["package"],
    "nvidia": json.loads(Path("pkgs/drivers/nvidia/version.json").read_text())["version"],
    "nixpkgs": json.loads(Path("flake.lock").read_text())["nodes"]["nixpkgs"]["locked"]["rev"],
}
Path("dist/unsigned/release.json").write_text(json.dumps(metadata, indent=2) + "\n")
PYMETA
(cd dist/unsigned && sha256sum kernel.efi glf-os.efi systemd-bootx64.efi modules.cer bundle.sha256 approved-modules.json release.json > SHA256SUMS)
