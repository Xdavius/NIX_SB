{ lib, aggregateModules, kernelPackages, approvedModules }:
# Cet arbre est independant de system.modulesTree et des modules du poste.
aggregateModules (
  [ (lib.getOutput "modules" kernelPackages.kernel) ]
  ++ builtins.attrValues (builtins.removeAttrs approvedModules [ "override" "overrideDerivation" ])
)
