{ runCommand }:
runCommand "glf-secureboot-certificate" {} ''
  mkdir -p "$out/share/secureboot"
  cp ${../../certificates/production/GLF.pem} "$out/share/secureboot/GLF.pem"
  cp ${../../certificates/production/GLF.cer} "$out/share/secureboot/GLF.cer"
''
