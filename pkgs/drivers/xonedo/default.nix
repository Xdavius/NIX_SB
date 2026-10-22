{ stdenv, lib, fetchFromGitHub, kernel, kernelModuleMakeFlags }:
stdenv.mkDerivation (finalAttrs: {
  pname = "xonedo";
  version = "unstable-2026-03-15";
  src = fetchFromGitHub {
    owner = "OpenGamingCollective";
    repo = "xonedo";
    rev = "982cbcb019ae4d2bee5ae69385223409ee555c88";
    hash = "sha256-0aSFgN8dK6X/+h2VEQjauJrsR4UzowShlNfE6nZPRhY=";
  };
  setSourceRoot = ''
    export sourceRoot=$(pwd)/${finalAttrs.src.name}
  '';
  nativeBuildInputs = kernel.moduleBuildDependencies;
  makeFlags = kernelModuleMakeFlags ++ [
    "-C" "${kernel.dev}/lib/modules/${kernel.modDirVersion}/build"
    "M=$(sourceRoot)"
    "VERSION=${finalAttrs.version}"
    "DEPMOD=true"
  ];
  enableParallelBuilding = true;
  buildFlags = [ "modules" ];
  # Installation Kbuild : conserver kmodigest et les certificats .ko.cer.
  # Les noms xone_* sont partages avec xone ; isoler les fichiers du catalogue.
  installFlags = [
    "INSTALL_MOD_PATH=${placeholder "out"}"
    "INSTALL_MOD_DIR=extra/xonedo"
  ];
  installTargets = [ "modules_install" ];
  meta = {
    description = "Pilote Xbox Wireless Dongle conservant la compatibilite avec xpad";
    homepage = "https://github.com/OpenGamingCollective/xonedo";
    license = lib.licenses.gpl2Plus;
    platforms = lib.platforms.linux;
    broken = kernel.kernelOlder "6.5";
  };
})
