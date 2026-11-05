{ pkgs, kernelVariant ? "default" }:
let
  variants = builtins.fromJSON (builtins.readFile ./kernel.json);
  valid = builtins.isAttrs variants
    && builtins.attrNames variants == [ "default" "latest" "upstream-latest" ]
    && builtins.all (name: builtins.isString variants.${name}) (builtins.attrNames variants);
  name = if builtins.hasAttr kernelVariant variants then variants.${kernelVariant}
    else throw "kernelVariant: variante inconnue: ${kernelVariant}";
in
if !valid then
  throw "pkgs/kernel/kernel.json: attendu default, latest et upstream-latest de type chaine"
else if !(builtins.hasAttr name pkgs) then
  throw "pkgs/kernel/kernel.json: attribut nixpkgs inconnu: ${name}"
else
  let selected = pkgs.${name};
  in if selected ? kernel && selected ? rebuildImage then selected
  else throw "pkgs/kernel/kernel.json: ${name} doit etre un ensemble kernelPackages avec rebuildImage"
