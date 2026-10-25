{ lib, fetchurl, runCommand, python3, openssl, sbsigntool, jq
, kernel, systemd, refind, rockyShim, releaseFile }:
let
  release = builtins.fromJSON (builtins.readFile releaseFile);
  valid = release.version == 2
    && builtins.match "[a-f0-9]{40}" release.commit != null
    && builtins.isString release.branch
    && builtins.elem release.profile [ "current" "testing" ];
  source = assert valid; fetchurl {
    name = "glf-signed-${release.commit}";
    inherit (release) url;
    hash = release.archiveHash;
  };
  # Identity only: do not realise the full module catalogue on consumers.
  # The pinned archive contains both this provenance and the signed image.
  expectedKernel = builtins.unsafeDiscardStringContext (toString kernel);
  bundle = runCommand "glf-secureboot-signed-${release.commit}" {
    nativeBuildInputs = [ python3 openssl sbsigntool jq ];
  } ''
    mkdir -p "$out"
    tar -xzf ${source} -C "$out"
    chmod -R u+w "$out"
    cd "$out"
    sha256sum --check SHA256SUMS
    test "$(jq -r .commit release.json)" = ${lib.escapeShellArg release.commit}
    test "$(jq -r .profile release.json)" = ${lib.escapeShellArg release.profile}
    test "$(jq -r .branch release.json)" = ${lib.escapeShellArg release.branch}
    openssl x509 -in GLF.pem -outform DER -out actual.cer
    cmp actual.cer ${../../certificates/production/GLF.cer}
    cmp GLF.cer ${../../certificates/production/GLF.cer}
    rm actual.cer
    for file in kernel.efi systemd-bootx64.efi; do
      sbverify --cert ${../../certificates/production/GLF.pem} "$file"
    done
    if test -f refind_x64.efi; then
      sbverify --cert ${../../certificates/production/GLF.pem} refind_x64.efi
    fi
    cmp shimx64.efi ${rockyShim}/share/efi/shimx64.efi
    cmp mmx64.efi ${rockyShim}/share/efi/mmx64.efi
    export PYTHONPATH=${../boot-tools/src}
    python3 - <<'PY'
from signing_protocol import pe_content
from pathlib import Path
if Path('refind_x64.efi').exists():
    assert pe_content('refind_x64.efi') == pe_content('${refind}/share/efi/refind_x64.efi'), 'rEFInd incompatible'
assert Path('store-paths.txt').read_text().splitlines()[0] == ${builtins.toJSON expectedKernel}, 'Noyau incompatible avec cette revision'
assert pe_content('systemd-bootx64.efi') == pe_content('${systemd}/lib/systemd/boot/efi/systemd-bootx64.efi'), 'Chargeur incompatible'
PY
  '';
in {
  inherit bundle;
  consumerApi = 1;
  # Explicit reproducibility audit; consumers do not depend on this output.
  verifiedBuild = runCommand "glf-secureboot-rebuilt-${release.commit}" {
    nativeBuildInputs = [ python3 ];
  } ''
    export PYTHONPATH=${../boot-tools/src}
    python3 - <<'PYVERIFY'
from signing_protocol import pe_content
assert pe_content('${bundle}/kernel.efi') == pe_content('${kernel}/bzImage'), 'Noyau incompatible avec cette revision'
PYVERIFY
    touch "$out"
  '';
  kernel = runCommand "glf-kernel-signed-${kernel.version}" {} ''
    mkdir -p "$out"
    ln -s ${bundle}/kernel.efi "$out/bzImage"
  '';
  refind = runCommand "glf-refind-signed-${release.commit}" {} ''
    test -f ${bundle}/refind_x64.efi
    mkdir -p "$out/share/efi"
    ln -s ${bundle}/refind_x64.efi "$out/share/efi/refind_x64.efi"
  '';
  bootloader = runCommand "glf-bootloader-signed-${release.commit}" {} ''
    mkdir -p "$out/share/efi"
    ln -s ${bundle}/systemd-bootx64.efi "$out/share/efi/systemd-bootx64.efi"
  '';
}
