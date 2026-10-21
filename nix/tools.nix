{ lib, stdenvNoCC, makeWrapper, python3, gh, openssl, sbsigntool, systemd, util-linux, efibootmgr }:
stdenvNoCC.mkDerivation {
  pname = "glf-boot-tools";
  version = "0.1.0";
  src = ../tools;
  nativeBuildInputs = [ makeWrapper ];
  dontBuild = true;
  installPhase = ''
    mkdir -p "$out/lib/glf-boot" "$out/bin"
    cp *.py "$out/lib/glf-boot/"
    makeWrapper ${python3}/bin/python3 "$out/bin/glf-github-sign" \
      --add-flags "$out/lib/glf-boot/github_sign.py" \
      --prefix PATH : ${lib.makeBinPath [ gh openssl sbsigntool ]}
    makeWrapper ${python3}/bin/python3 "$out/bin/glf-install-boot" \
      --add-flags "$out/lib/glf-boot/install_boot.py" \
      --prefix PATH : ${lib.makeBinPath [ sbsigntool systemd util-linux efibootmgr ]}
  '';
}
