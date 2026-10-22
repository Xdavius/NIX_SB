{ v4l2loopback }:
v4l2loopback.overrideAttrs (old: {
  # L'index est produit par aggregateModules pour l'arbre complet.
  makeFlags = (old.makeFlags or []) ++ [ "DEPMOD=true" ];
})
