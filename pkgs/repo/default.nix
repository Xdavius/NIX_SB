# Liste de confiance GLF : toute modification exige une revue du depot.
# Les sources, revisions et hashes sont fixes dans chaque definition.
{ kernelPackages }:
{
  hid-fanatek = kernelPackages.callPackage ./hid-fanatek { };
  new-lg4ff = kernelPackages.callPackage ./new-lg4ff { };
}
