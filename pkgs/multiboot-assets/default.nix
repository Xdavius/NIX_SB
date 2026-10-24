{ runCommand, refind, librsvg, imagemagick }:
runCommand "glf-multiboot-assets" {
  nativeBuildInputs = [ librsvg imagemagick ];
} ''
  mkdir -p "$out/themes/glfos"
  cp -r ${refind}/share/refind/icons "$out/icons"
  rsvg-convert ${./assets/glf-bootloader.svg} -o banner.png
  # RGB 8 bits, opaque, non entrelace ; compression sans perte.
  magick banner.png -alpha off -strip -depth 8 -interlace none \
    -define png:compression-level=9 -define png:compression-filter=5 \
    PNG24:"$out/themes/glfos/glf-bootloader.png"
  cp ${./assets/glfos-logo.png} "$out/themes/glfos/glfos.png"
''
