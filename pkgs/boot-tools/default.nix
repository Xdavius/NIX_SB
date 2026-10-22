{ lib, stdenvNoCC, makeWrapper, python3, sbsigntool, systemd, util-linux, efibootmgr }:
stdenvNoCC.mkDerivation {
  pname = "glf-secureboot";
  version = "0.3.0";
  src = ./src;
  nativeBuildInputs = [ makeWrapper ];
  dontBuild = true;
  installPhase = ''
    runHook preInstall
    mkdir -p "$out/lib/glf-secureboot" "$out/bin"
    cp *.py "$out/lib/glf-secureboot/"
    makeWrapper ${python3}/bin/python3 "$out/bin/glf-secureboot-install" \
      --add-flags "$out/lib/glf-secureboot/install_boot.py" \
      --prefix PATH : ${lib.makeBinPath [ sbsigntool systemd util-linux efibootmgr ]}
    runHook postInstall
  '';
  meta.description = "Installation du noyau signe GLF avec initrd local";
}
