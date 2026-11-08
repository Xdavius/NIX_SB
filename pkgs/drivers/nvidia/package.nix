# Version et hashes NVIDIA geres par NIX_SB, communs aux outils et modules.
{ nvidiaPackages, lib, stdenv, python3, patchelf }:
let
  driver = nvidiaPackages.mkDriver (builtins.fromJSON (builtins.readFile ./version.json));
  script = value: if value == null then "" else value;
in driver.overrideAttrs (old: {
  postInstall = script (old.postInstall or null) + "\n" + builtins.readFile ./install-extras.sh;
  doInstallCheck = true;
  nativeInstallCheckInputs = (old.nativeInstallCheckInputs or []) ++ [ python3 patchelf ];
  postInstallCheck = script (old.postInstallCheck or null) + ''
    python3 ${./check-install.py} "$out" "$bin" \
      ${lib.optionalString stdenv.hostPlatform.isx86_64 "--vulkansc"}
  '';
})
