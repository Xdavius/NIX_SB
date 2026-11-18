# Les variantes publiees gardent le pin local ; upstream-latest suit le channel.
{ nvidiaPackages, kernelVariant ? "default" }:
if builtins.elem kernelVariant [ "default" "latest" ] then
  nvidiaPackages.mkDriver (builtins.fromJSON (builtins.readFile ./version.json))
else if kernelVariant == "upstream-latest" then
  nvidiaPackages.latest
else
  throw "NVIDIA: variante noyau inconnue: ${kernelVariant}"
