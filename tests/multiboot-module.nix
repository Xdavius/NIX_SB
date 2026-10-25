{ pkgs, sb }:
let
  evaluate = options: (import "${pkgs.path}/nixos/lib/eval-config.nix" {
    system = "x86_64-linux";
    inherit pkgs;
    modules = [ ../modules/multiboot.nix {
      system.stateVersion = "26.05";
      glf.secureboot.packageSet = sb // { signed = { bundle = pkgs.emptyDirectory; kernel = pkgs.emptyDirectory; }; };
      boot.loader.efi.canTouchEfiVariables = false;
      fileSystems."/" = { device = "none"; fsType = "tmpfs"; };
    } options ];
  }).config;
  enabled = evaluate { glf.multiboot.enable = true; };
  disabled = evaluate {};
  optedOut = evaluate { glf.secureboot.enable = false; };
in
assert enabled.boot.loader.external.enable;
assert !enabled.boot.loader.systemd-boot.enable;
assert !enabled.boot.loader.grub.enable;
assert enabled.glf.multiboot.installFallback;
assert enabled.glf.multiboot.configurationLimit == 10;
assert enabled.boot.kernelPackages.kernel.outPath == sb.kernelPackages.kernel.outPath;
assert builtins.elem "module.sig_enforce=1" enabled.boot.kernelParams;
assert builtins.elem "lockdown=integrity" enabled.boot.kernelParams;
assert disabled.glf.secureboot.enable;
assert disabled.boot.loader.external.enable;
assert !optedOut.glf.secureboot.enable;
assert !optedOut.boot.loader.external.enable;
assert !disabled.glf.multiboot.enable;
assert pkgs.lib.hasInfix "glf-secureboot.json" enabled.system.systemBuilderCommands;
assert pkgs.lib.hasInfix "glf-secureboot-install" enabled.boot.loader.external.installHook.text;
pkgs.runCommand "glf-multiboot-module-check" {} ''
  echo "Module Secure Boot et bascule multiboot/systemd-boot evalues" > "$out"
''
