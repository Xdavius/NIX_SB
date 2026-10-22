{ pkgs }:
let
  selection = builtins.fromJSON (builtins.readFile ../../kernel.json);
  name = selection.package;
in
if builtins.attrNames selection != [ "package" ] || !builtins.isString name then
  throw "kernel.json: attendu un champ package de type chaine"
else if !(builtins.hasAttr name pkgs) then
  throw "kernel.json: attribut nixpkgs inconnu: ${name}"
else
  let selected = pkgs.${name};
  in if selected ? kernel && selected ? rebuildImage then selected
  else throw "kernel.json: ${name} doit etre un ensemble kernelPackages avec rebuildImage"
