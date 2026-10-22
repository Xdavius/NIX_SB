#!/usr/bin/env bash
# Execute uniquement depuis le checkout de confiance, sans cle de signature.
set -euo pipefail
[[ ${REQUEST_TAG:-} =~ ^glf-sign-[a-f0-9]{32}$ ]] || exit 1
[[ ${REQUEST_SHA256:-} =~ ^[a-f0-9]{64}$ ]] || exit 1
mkdir -p dist
mkdir dist/unsigned
for file in kernel.efi glf-os.efi systemd-bootx64.efi request.json; do
  gh release download "$REQUEST_TAG" --repo "$GITHUB_REPOSITORY" \
    --pattern "$file" --dir dist/unsigned
done
# Le commit execute de NIX_SB definit la confiance, jamais la demande du client.
kernel=$(nix build --no-update-lock-file --no-link --print-out-paths .#kernel)
boot=$(nix build --no-update-lock-file --no-link --print-out-paths .#systemd-boot)
python3 ci/validate-request.py dist/unsigned --sha256 "$REQUEST_SHA256" \
  --kernel "$kernel/bzImage" --bootloader "$boot/systemd-bootx64.efi" \
  --stub "$GLF_TEST_STUB" --ukify "$GLF_TEST_UKIFY"
