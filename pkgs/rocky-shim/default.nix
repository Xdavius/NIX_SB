{ stdenvNoCC, fetchurl, libarchive, sbsigntool, binutils, lib }:

stdenvNoCC.mkDerivation {
  pname = "rocky-shim-signed";
  version = "16.1-2.el10";
  src = fetchurl {
    url = "https://download.rockylinux.org/pub/rocky/10.2/BaseOS/x86_64/os/Packages/s/shim-x64-16.1-2.el10.x86_64.rpm";
    hash = "sha256-o/GGgXqlzDaHsaNdKicjK79/HVONtGShPWymL4r+xeI=";
  };
  nativeBuildInputs = [ libarchive sbsigntool binutils ];
  unpackPhase = ''
    mkdir source
    cd source
    bsdtar -xf "$src"
  '';
  dontConfigure = true;
  dontBuild = true;
  # Les binaires PE signes ne doivent etre ni strippes ni patches.
  dontFixup = true;
  installPhase = ''
    mkdir -p "$out/share/efi" "$out/share/doc"
    for file in shimx64.efi mmx64.efi; do
      cp "boot/efi/EFI/rocky/$file" "$out/share/efi/$file"
      cmp "boot/efi/EFI/rocky/$file" "$out/share/efi/$file"
      sbverify --list "$out/share/efi/$file" > "$out/share/doc/$file.signatures.txt"
      grep -q '^signature 1' "$out/share/doc/$file.signatures.txt"
      objcopy --dump-section .sbat="$out/share/doc/$file.sbat.csv" "$out/share/efi/$file" inspected.efi
      rm inspected.efi
    done
    (cd "$out/share/efi" && sha256sum shimx64.efi mmx64.efi > SHA256SUMS)
  '';
  meta = {
    description = "Shim et MokManager signes, extraits sans modification du RPM officiel Rocky Linux";
    homepage = "https://rockylinux.org";
    license = lib.licenses.bsd2;
    platforms = [ "x86_64-linux" ];
    sourceProvenance = [ lib.sourceTypes.binaryNativeCode ];
  };
}
