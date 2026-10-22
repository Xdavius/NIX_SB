{ lib, stdenvNoCC, makeWrapper, python3, gh, openssl, sbsigntool, systemd, util-linux, efibootmgr }:
stdenvNoCC.mkDerivation {
  pname = "glf-secureboot";
  version = "0.2.0";
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
    makeWrapper ${python3}/bin/python3 "$out/bin/glf-secureboot-sign" \
      --add-flags "$out/lib/glf-secureboot/github_sign.py" \
      --prefix PATH : ${lib.makeBinPath [ gh openssl sbsigntool ]}
    runHook postInstall
  '';
  meta.description = "Assemblage et installation UKI avec un signataire externe";
}
