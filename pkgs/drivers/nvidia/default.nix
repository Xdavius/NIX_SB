# GLF-OS utilise les modules NVIDIA open ; les composants utilisateurs sont
# exposes separement par sb.nvidia, depuis la meme definition de version.
{ callPackage }:
(callPackage ./package.nix {}).open
