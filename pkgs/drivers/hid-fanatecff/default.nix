{
  stdenv,
  fetchFromGitHub,
  kernel,
  linuxConsoleTools,
  kernelModuleMakeFlags ? kernel.commonMakeFlags ++ [
    "KBUILD_OUTPUT=${kernel.dev}/lib/modules/${kernel.modDirVersion}/build"
  ],
}:

stdenv.mkDerivation rec {
  pname = "hid-fanatecff";
  version = "0.2.3";
  name = "${pname}-${version}-${kernel.modDirVersion}";

  src = fetchFromGitHub {
    owner = "gotzl";
    repo = pname;
    rev = version;
    sha256 = "sha256-lJ+Pn1OLgZK+T1dsV1mwzAwJJgsouFFwDH7bFUD1SGI=";
  };

  hardeningDisable = [
    "pic"
    "format"
  ];
  nativeBuildInputs = kernel.moduleBuildDependencies;

  postPatch = ''
    # Use Kbuild installation so the kernel's signing command also runs.
    substituteInPlace Makefile --replace-fail \
        'cp -v hid-fanatec.ko ''${MODULEDIR}' \
        '$(MAKE) -C $(KERNEL_SRC) M=$$PWD modules_install'
    substituteInPlace Makefile --replace-fail "/etc/udev/rules.d" "$out/lib/udev/rules.d"
    substituteInPlace fanatec.rules --replace-fail "/usr/bin/evdev-joystick" "${linuxConsoleTools}/bin/evdev-joystick" --replace-fail "/bin/sh" "${stdenv.shell}"
    sed -i '/depmod/d' Makefile
  '';

  preInstall = ''
    mkdir -p "$out/lib/udev/rules.d"
  '';

  makeFlags = kernelModuleMakeFlags ++ [
    "KVERSION=${kernel.modDirVersion}"
    "KERNEL_SRC=${kernel.dev}/lib/modules/${kernel.modDirVersion}/build"
    "INSTALL_MOD_PATH=${placeholder "out"}"
    "INSTALL_MOD_DIR=kernel/drivers/hid"
    "DEPMOD=true"
  ];
}
