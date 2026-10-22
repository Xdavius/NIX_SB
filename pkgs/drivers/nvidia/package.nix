# Version et hashes NVIDIA geres par NIX_SB, communs aux outils et modules.
{ nvidiaPackages }:
nvidiaPackages.mkDriver (builtins.fromJSON (builtins.readFile ./version.json))
