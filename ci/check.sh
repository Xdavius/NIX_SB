#!/usr/bin/env bash
set -euo pipefail
for script in ci/*.sh; do bash -n "$script"; done
shellcheck ci/*.sh
actionlint
flake_ref=${GLF_FLAKE_REF:-.}
nix flake check "$flake_ref" --no-build --no-update-lock-file
kernel=$(nix eval --raw "$flake_ref#packages.x86_64-linux.kernel.outPath")
uki_kernel=$(nix eval --raw "$flake_ref#nixosConfigurations.prototype.config.boot.uki.settings.UKI.Linux")
[[ $uki_kernel == "$kernel/bzImage" ]] || { echo 'UKI ne reference pas le noyau enrichi' >&2; exit 1; }
nix eval --raw "$flake_ref#packages.x86_64-linux.uki.drvPath"
python3 ci/test-signing.py "$GLF_TEST_STUB"
python3 tests/test_boot.py
python3 tests/test_github_sign.py
python3 tests/test_signing_policy.py
nix build --no-update-lock-file "$flake_ref#enrollment" --out-link result-enrollment
(cd result-enrollment && sha256sum --check SHA256SUMS)
