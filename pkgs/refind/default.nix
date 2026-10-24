{ lib, stdenv, fetchzip, fetchurl, edk2, nasm, python3 }:
let
  toolchain = if lib.versionAtLeast edk2.version "202608" then "GCC" else "GCC5";
  # rEFInd 0.14.2 still uses the IntelFramework interfaces removed from EDK2.
  sdk = fetchzip {
    url = "https://github.com/tianocore/edk2/archive/refs/tags/edk2-stable201903.tar.gz";
    sha256 = "15hj5zb6074r6k5i34q4wqqiyfsf2sj40s7c1maqfjychf5vz1rj";
  };
in stdenv.mkDerivation {
  pname = "glf-refind";
  version = "0.14.2";
  src = fetchurl {
    url = "mirror://sourceforge/project/refind/0.14.2/refind-src-0.14.2.tar.gz";
    hash = "sha256-99k86A2na4bFZygeoiW2qHkHzob/dyM8k1elIsEVyPA=";
  };
  patches = [ ./submenu-on-select.patch ];
  postPatch = ''
    # Match the warning policy used by the earlier EDK2 GCC5 toolchain.
    substituteInPlace refind.inf --replace-fail '-Os -DEFIX64' \
      '-Os -Wno-unused-but-set-variable -Wno-unused-const-variable -DEFIX64'
  '';
  nativeBuildInputs = [ nasm python3 ];
  hardeningDisable = [ "all" ];
  dontConfigure = true;
  dontStrip = true;
  buildPhase = ''
    runHook preBuild
    refindSource="$PWD"
    cp -r ${sdk} ../edk2
    chmod -R u+w ../edk2
    cd ../edk2
    rm -rf BaseTools
    cp -r ${edk2}/BaseTools .
    chmod -R u+w BaseTools
    ln -s "$refindSource" RefindPkg
    export WORKSPACE="$PWD"
    export EDK_TOOLS_PATH="$PWD/BaseTools"
    export PYTHON_COMMAND=python3
    source ${edk2}/edksetup.sh BaseTools
    # Modern BaseTools enable stack guards absent from the legacy SDK runtime.
    substituteInPlace Conf/tools_def.txt --replace-fail '-fstack-protector' '-fno-stack-protector'
    # Shim's memory protections require page-aligned PE sections.
    substituteInPlace Conf/tools_def.txt --replace-fail 'common-page-size=0x40' 'common-page-size=0x1000'
    build -a X64 -b RELEASE -t ${toolchain} -p RefindPkg/RefindPkg.dsc -m RefindPkg/refind.inf -n "$NIX_BUILD_CORES"
    cp Build/Refind/RELEASE_${toolchain}/X64/refind.efi "$refindSource/refind_x64.efi"
    cd "$refindSource"
    objcopy --set-section-alignment '.sbat=4096' --add-section .sbat=refind-sbat.csv \
      --adjust-section-vma .sbat+0x1000000 refind_x64.efi
    runHook postBuild
  '';
  installPhase = ''
    mkdir -p "$out/share/efi" "$out/share/refind"
    cp refind_x64.efi "$out/share/efi/"
    cp -r icons "$out/share/refind/"
  '';
  meta = {
    description = "TianoCore rEFInd with opt-in submenu on selection";
    license = lib.licenses.gpl3Plus;
    platforms = [ "x86_64-linux" ];
  };
}
