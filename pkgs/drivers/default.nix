{ lib, kernelPackages, catalogueFile ? ./catalogue.json }:
let
  catalogue = builtins.fromJSON (builtins.readFile catalogueFile);
  base = builtins.dirOf catalogueFile;
  fail = name: message: throw "Catalogue drivers (${name}): ${message}";
  resolve = name: entry:
    let
      keys = if builtins.isAttrs entry then builtins.attrNames entry else [];
      package =
        if keys == [ "package" ] && builtins.isString entry.package then
          let
            parts = lib.splitString "." entry.package;
          in
          if entry.package != "" && lib.hasAttrByPath parts kernelPackages then
            lib.getAttrFromPath parts kernelPackages
          else fail name "attribut kernelPackages introuvable: ${entry.package}"
        else if keys == [ "path" ] && builtins.isString entry.path then
          if !(lib.hasPrefix "./" entry.path)
            || builtins.elem ".." (lib.splitString "/" entry.path) then
            fail name "path doit etre relatif au catalogue, sans '..'"
          else
            let source = base + "/${entry.path}";
            in if builtins.pathExists source then kernelPackages.callPackage source { }
            else fail name "definition introuvable: ${entry.path}"
        else fail name "attendu exactement 'package' ou 'path' de type chaine";
    in
    if lib.isDerivation package then package
    else fail name "l'entree ne designe pas un paquet";
in
if builtins.isAttrs catalogue then
  if catalogue ? override || catalogue ? overrideDerivation then
    throw "Catalogue drivers: override et overrideDerivation sont des noms reserves"
  else lib.mapAttrs resolve catalogue
else throw "Catalogue drivers: la racine JSON doit etre un objet"
