{ pkgs, sb, target }:
let
  inherit (pkgs) lib;
  kernelPackages = sb.kernelPackages;
  loader = import ../pkgs/drivers;
  resolve = name: loader {
    inherit lib kernelPackages;
    catalogueFile = ./fixtures/catalogues + "/${name}.json";
  };
  rejects = name: !(builtins.tryEval (builtins.deepSeq (resolve name) true)).success;
  cfg = target.config;
in
assert rejects "not-object";
assert rejects "empty-entry";
assert rejects "both";
assert rejects "missing-package";
assert rejects "not-package";
assert rejects "wrong-type";
assert rejects "parent-path";
assert rejects "absolute-path";
assert rejects "missing-path";
assert rejects "reserved";
assert (resolve "valid").test.outPath == kernelPackages.new-lg4ff.outPath;
assert sb.drivers.new-lg4ff.outPath != kernelPackages.new-lg4ff.outPath;
assert sb.drivers.hid-fanatecff.outPath != kernelPackages.hid-fanatecff.outPath;
assert lib.hasInfix "DEPMOD=true" (lib.concatStringsSep " " sb.drivers.hid-fanatecff.makeFlags);
assert sb.drivers.new-lg4ff.outPath == (kernelPackages.callPackage
  ../pkgs/drivers/new-lg4ff {}).outPath;
assert cfg.boot.kernelPackages.kernel.outPath == sb.kernelPackages.kernel.outPath;
assert sb.kernelPackages.kernel.version == sb.kernel.version;
assert builtins.attrNames sb.drivers == [
  "hid-fanatecff" "hid-tmff2" "new-lg4ff" "nvidia-open" "openrazer" "v4l2loopback" "xone" "xonedo" "xpad-noone" "xpadneo"
];
assert sb.drivers.nvidia-open.outPath == sb.nvidia.open.outPath;
assert sb.drivers.nvidia-open.version == "${sb.nvidia.version}-${kernelPackages.kernel.version}";
assert sb.nvidia.version == (builtins.fromJSON (builtins.readFile ../pkgs/drivers/nvidia/version.json)).version;
assert builtins.elem "INSTALL_MOD_DIR=extra/xonedo" sb.drivers.xonedo.installFlags;
assert sb.drivers.xonedo.installTargets == [ "modules_install" ];
assert sb.drivers.xone.outPath == kernelPackages.xone.outPath;
assert sb.drivers.xpadneo.outPath == kernelPackages.xpadneo.outPath;
assert sb.drivers.xpad-noone.outPath == kernelPackages.xpad-noone.outPath;
assert sb.drivers.openrazer.outPath == kernelPackages.openrazer.outPath;
assert sb.drivers.hid-tmff2.outPath == kernelPackages.hid-tmff2.outPath;
assert builtins.elem "DEPMOD=true" sb.drivers.v4l2loopback.makeFlags;
assert sb.kernel.moduleCertificates == "${sb.modulesTree}/lib/modules/${kernelPackages.kernel.modDirVersion}/modules.cer";
assert (pkgs.callPackage ../pkgs/kernel {
  inherit kernelPackages;
  approvedModules = sb.drivers;
}).outPath == sb.kernel.outPath;
assert cfg.boot.uki.settings.UKI.Linux == "${sb.kernel}/bzImage";
assert builtins.elem "module.sig_enforce=1" cfg.boot.kernelParams;
assert builtins.elem "lockdown=integrity" cfg.boot.kernelParams;
assert sb.boot-tools.pname == "glf-secureboot";
assert sb.boot-tools.glfInstallerApi == 1;
pkgs.runCommand "nix-sb-package-contract" {} ''
  echo "Catalogue valide, sources nixpkgs reutilisees et noyau coherent" > "$out"
''
