{ lib, callPackage, runCommand, writeText, kernelPackages, approvedModules,
  modulesTree ? callPackage ../modules-tree { inherit kernelPackages approvedModules; }
}:
let
  kernel = kernelPackages.kernel;
  manifest = writeText "approved-modules.json" (builtins.toJSON {
    kernel = toString (lib.getOutput "modules" kernel);
    modules = lib.mapAttrs (_: package: toString package) (builtins.removeAttrs approvedModules [ "override" "overrideDerivation" ]);
  });
in runCommand "glf-module-certificates" {} ''
  mkdir -p "$out"
  cp ${modulesTree}/lib/modules/${kernel.modDirVersion}/modules.cer "$out/modules.cer"
  test -s "$out/modules.cer"
  sha256sum "$out/modules.cer" | cut -d' ' -f1 > "$out/bundle.sha256"
  cp ${manifest} "$out/approved-modules.json"
''
