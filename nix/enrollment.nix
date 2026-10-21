{ runCommand, rockyShim, openssl }:

runCommand "glf-test-enrollment-x64" { nativeBuildInputs = [ openssl ]; } ''
  mkdir -p "$out/EFI/BOOT" "$out/certificates" "$out/info"
  cp ${rockyShim}/share/efi/shimx64.efi "$out/EFI/BOOT/BOOTX64.EFI"
  cp ${rockyShim}/share/efi/mmx64.efi "$out/EFI/BOOT/mmx64.efi"
  # Support d'enrolement uniquement : le second etage ouvre MokManager.
  # Ce nom est celui attendu par le shim Rocky ; aucun binaire n'est modifie.
  cp ${rockyShim}/share/efi/mmx64.efi "$out/EFI/BOOT/grubx64.efi"
  cp ${../certificates/GLF-TEST.cer} "$out/certificates/GLF-TEST.cer"
  cp ${../docs/ENROLLMENT.md} "$out/README.md"
  cp ${rockyShim}/share/doc/* "$out/info/"
  openssl x509 -inform DER -in "$out/certificates/GLF-TEST.cer" \
    -noout -subject -dates -fingerprint -sha256 > "$out/info/GLF-TEST.txt"
  cmp "$out/EFI/BOOT/BOOTX64.EFI" ${rockyShim}/share/efi/shimx64.efi
  cmp "$out/EFI/BOOT/grubx64.efi" "$out/EFI/BOOT/mmx64.efi"
  cd "$out"
  sha256sum EFI/BOOT/* certificates/GLF-TEST.cer > SHA256SUMS
''
