#!/usr/bin/env bash
set -euo pipefail
flake_ref=${GLF_FLAKE_REF:-path:$PWD}
profile=${GLF_CHANNEL:-current}
case "$profile" in current) prefix="" ;; testing) prefix="testing-" ;; *) exit 1 ;; esac
mkdir -p dist
[[ ! -e dist/unsigned ]] || { echo "dist/unsigned existe deja" >&2; exit 1; }
mkdir dist/unsigned
nix build --no-update-lock-file "$flake_ref#${prefix}kernel" "$flake_ref#${prefix}certificates" "$flake_ref#${prefix}systemd-boot" "$flake_ref#${prefix}rocky-shim" "$flake_ref#${prefix}refind" --out-link result
kernel=$(readlink -f result)
certs=$(readlink -f result-1)
sdboot=$(readlink -f result-2)
shim=$(readlink -f result-3)
refind=$(readlink -f result-4)
cp --remove-destination "$refind/share/efi/refind_x64.efi" dist/unsigned/
cp --remove-destination "$sdboot/systemd-bootx64.efi" dist/unsigned/
cp --remove-destination "$kernel/bzImage" dist/unsigned/kernel.efi
cp "$shim/share/efi/shimx64.efi" "$shim/share/efi/mmx64.efi" dist/unsigned/
cp --remove-destination "$certs/modules.cer" "$certs/bundle.sha256" dist/unsigned/
cp --remove-destination "$certs/approved-modules.json" dist/unsigned/
cp flake.lock dist/unsigned/flake.lock
# References des closures non signees pour diagnostic.
nix path-info --recursive --json --json-format 1 "$kernel" "$certs" "$sdboot" "$shim" "$refind" > dist/unsigned/nix-closure.json
printf '%s\n' "$kernel" "$certs" "$sdboot" "$shim" "$refind" > dist/unsigned/store-paths.txt
export GLF_RELEASE_BRANCH="${GITHUB_REF_NAME:-$(git branch --show-current)}"
export GLF_RELEASE_COMMIT="${GITHUB_SHA:-$(git rev-parse HEAD)}"
python3 - <<'PYMETA'
import json
import os
from pathlib import Path
from ci.channels import channel_info
channels = channel_info(json.loads(Path("flake.lock").read_text()), os.environ.get("GLF_CHANNEL", "current"))
metadata = {
    "profile": os.environ.get("GLF_CHANNEL", "current"),
    "branch": os.environ["GLF_RELEASE_BRANCH"],
    "commit": os.environ["GLF_RELEASE_COMMIT"],
    "kernel": json.loads(Path("kernel.json").read_text())["package"],
    "nvidia": json.loads(Path("pkgs/drivers/nvidia/version.json").read_text())["version"],
    "nixpkgs": channels["nixpkgs"]["rev"],
    "channels": channels,
}
Path("dist/unsigned/release.json").write_text(json.dumps(metadata, indent=2) + "\n")
PYMETA
(cd dist/unsigned && sha256sum kernel.efi refind_x64.efi systemd-bootx64.efi shimx64.efi mmx64.efi modules.cer bundle.sha256 approved-modules.json release.json flake.lock > SHA256SUMS)
