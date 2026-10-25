{ lib, stdenvNoCC, makeWrapper, python3, sbsigntool, systemd, util-linux, efibootmgr, multibootAssets }:
stdenvNoCC.mkDerivation {
  pname = "glf-secureboot";
  version = "0.5.0";
  # Consumers can drop their installer patches once this capability is present.
  passthru.glfInstallerApi = 1;
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
    makeWrapper ${python3}/bin/python3 "$out/bin/glf-multiboot" \
      --add-flags "$out/lib/glf-secureboot/multiboot.py" \
      --prefix PATH : ${lib.makeBinPath [ sbsigntool systemd util-linux efibootmgr ]} \
      --set GLF_MULTIBOOT_ASSETS ${multibootAssets}
    wrapProgram "$out/bin/glf-secureboot-install" --set GLF_MULTIBOOT_ASSETS ${multibootAssets}
    runHook postInstall
  '';
  meta.description = "Installation du noyau signe GLF avec initrd local";
}
