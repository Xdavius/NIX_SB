{ callPackage, kernelPackages, approvedModules, modulesTree ? callPackage ../modules-tree {
  inherit kernelPackages approvedModules;
} }:
# Image uniquement : les drivers utilisent toujours le noyau de base.
if kernelPackages ? rebuildImage then
  kernelPackages.rebuildImage { inherit modulesTree; }
else
  throw "NIX_SB: kernelPackages doit fournir rebuildImage (nixpkgs avec kmodigest)"
