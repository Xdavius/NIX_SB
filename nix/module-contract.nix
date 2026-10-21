{ pkgs, nixpkgs, self, target, system }:
let
  customized = target.extendModules {
    modules = [ ({ lib, ... }: {
      networking.hostName = lib.mkForce "glf-real-machine";
      fileSystems."/".device = lib.mkForce "/dev/disk/by-uuid/machine-specific";
      boot.kernelParams = [ "glf.machine=specific" ];
    }) ];
  };
  disabled = nixpkgs.lib.nixosSystem {
    inherit system;
    modules = [
      self.nixosModules.default
      # GLF-OS possede deja cette option, active par defaut.
      ({ lib, ... }: {
        options.glf.boot.enable = lib.mkOption { type = lib.types.bool; default = true; };
      })
    ];
  };
  cfg = customized.config;
  unapproved = target.extendModules {
    modules = [ ({ pkgs, ... }: { boot.extraModulePackages = [ pkgs.hello ]; }) ];
  };
  injectedTree = target.extendModules {
    modules = [ ({ pkgs, ... }: { system.modulesTree = [ pkgs.hello ]; }) ];
  };
in
assert builtins.any (entry: !entry.assertion && pkgs.lib.hasInfix "module externe non approuve" entry.message) unapproved.config.assertions;
assert injectedTree.config.system.build.glfKernel.outPath == target.config.system.build.glfKernel.outPath;
assert disabled.config.glf-securebootUKI.enable == false;
assert disabled.config.glf.boot.enable == true;
assert !(disabled.config.system.build ? glfKernel);
assert cfg.networking.hostName == "glf-real-machine";
assert cfg.fileSystems."/".device == "/dev/disk/by-uuid/machine-specific";
assert builtins.elem "glf.machine=specific" cfg.boot.kernelParams;
assert builtins.elem "module.sig_enforce=1" cfg.boot.kernelParams;
assert cfg.boot.loader.systemd-boot.enable;
assert cfg.boot.uki.settings.UKI.Linux == "${cfg.system.build.glfKernel}/${cfg.system.boot.loader.kernelFile}";
assert (pkgs.callPackage ../default.nix { }).pname == "glf-boot-tools";
pkgs.runCommand "glf-module-contract" { } ''
  echo "Module opt-in, configuration machine preservee et paquet callPackage disponibles" > "$out"
''
