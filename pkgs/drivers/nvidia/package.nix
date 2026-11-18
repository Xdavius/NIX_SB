# Chaque variante definit un pin ou un attribut de nvidiaPackages dans le JSON.
{ nvidiaPackages, kernelVariant ? "default" }:
let
  variants = builtins.fromJSON (builtins.readFile ./version.json);
  selected = if builtins.hasAttr kernelVariant variants then variants.${kernelVariant}
    else throw "NVIDIA: variante noyau inconnue: ${kernelVariant}";
in
if selected ? package then
  nvidiaPackages.${selected.package}
else
  nvidiaPackages.mkDriver selected
