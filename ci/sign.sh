#!/usr/bin/env bash
# Ne jamais activer xtrace dans ce script ou son appelant.
set +x
set -euo pipefail
umask 077
: "${GLF_SIGNING_KEY_PEM:?Secret de signature absent}"
: "${GLF_SIGNING_CERT_PEM:?Certificat GLF absent}"
: "${GLF_CERT_SHA256:?Empreinte GLF attendue absente}"
[[ ! -e dist/signed ]] || { echo 'dist/signed existe deja' >&2; exit 1; }
secret_dir=$(mktemp -d)
trap 'rm -rf -- "$secret_dir"' EXIT
printf '%s\n' "$GLF_SIGNING_KEY_PEM" > "$secret_dir/key.pem"
printf '%s\n' "$GLF_SIGNING_CERT_PEM" > "$secret_dir/cert.pem"
unset GLF_SIGNING_KEY_PEM GLF_SIGNING_CERT_PEM
actual=$(openssl x509 -in "$secret_dir/cert.pem" -noout -fingerprint -sha256)
actual=${actual#*=}
expected=${GLF_CERT_SHA256//:/}
actual=${actual//:/}
[[ ${actual^^} == "${expected^^}" ]] || { echo 'Certificat GLF inattendu' >&2; exit 1; }
openssl pkey -in "$secret_dir/key.pem" -passin pass: -pubout -out "$secret_dir/key.pub" 2>/dev/null
openssl x509 -in "$secret_dir/cert.pem" -pubkey -noout > "$secret_dir/cert.pub"
cmp -s "$secret_dir/key.pub" "$secret_dir/cert.pub" || { echo 'Cle et certificat incompatibles' >&2; exit 1; }
(cd dist/unsigned && sha256sum --check SHA256SUMS)
mkdir -p dist/signed
for file in kernel.efi glf-os.efi systemd-bootx64.efi; do
  sbsign --key "$secret_dir/key.pem" --cert "$secret_dir/cert.pem" \
    --output "dist/signed/$file" "dist/unsigned/$file"
  sbverify --cert "$secret_dir/cert.pem" "dist/signed/$file"
done
openssl x509 -in "$secret_dir/cert.pem" -outform DER -out dist/signed/GLF.cer
for file in modules.cer bundle.sha256 approved-modules.json nix-closure.json store-paths.txt; do
  if [[ -f dist/unsigned/$file ]]; then cp "dist/unsigned/$file" dist/signed/; fi
done
(cd dist/signed && sha256sum kernel.efi glf-os.efi systemd-bootx64.efi GLF.cer > SHA256SUMS)
