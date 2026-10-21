"""Boot the real kernel via Rocky shim and systemd-boot with a test key in MOK.

Uses emulated firmware and an ephemeral key, never host EFI variables or GLF's key.
"""
import os
import lzma
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


def run(*args, **kw):
    return subprocess.run([str(x) for x in args], check=True, **kw)


kernel = Path(sys.argv[1]).resolve(strict=True)
with tempfile.TemporaryDirectory(prefix="glf-uefi-") as temp:
    root = Path(temp)
    key, cert = root / "key.pem", root / "cert.pem"
    run("openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "1",
        "-subj", "/CN=GLF VM DISPOSABLE TEST/", "-keyout", key, "-out", cert,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    initrd_root = root / "root"
    (initrd_root / "bin").mkdir(parents=True)
    shutil.copyfile(os.environ["GLF_VM_BUSYBOX"], initrd_root / "bin/busybox")
    (initrd_root / "bin/busybox").chmod(0o755)
    module = next(Path(os.environ["GLF_VM_MODULES"]).glob("lib/modules/*/kernel/fs/efivarfs/efivarfs.ko*"))
    module_data = subprocess.check_output(["zstd", "-dc", str(module)]) if module.suffix == ".zst" else module.read_bytes()
    if module.suffix == ".xz":
        module_data = lzma.decompress(module_data)
    (initrd_root / "efivarfs.ko").write_bytes(module_data)
    corrupt = bytearray(module_data)
    index = corrupt.index(b"description=") + len(b"description=")
    corrupt[index] ^= 1
    (initrd_root / "corrupt.ko").write_bytes(corrupt)
    driver_commands = []
    installed = set()
    for driver in ('hid-fanatec', 'hid-logitech-new'):
        version = next((Path(os.environ['GLF_VM_MODULES']) / 'lib/modules').iterdir()).name
        deps = subprocess.check_output(['modprobe', '--show-depends', '-d', os.environ['GLF_VM_MODULES'],
                                        '-S', version, driver], text=True)
        for line in deps.splitlines():
            if not line.startswith('insmod '):
                continue
            source = Path(line.split()[1])
            if source in installed:
                continue
            installed.add(source)
            name = f'driver-{len(installed)}.ko'
            data = source.read_bytes()
            if source.suffix == '.xz':
                data = lzma.decompress(data)
            elif source.suffix == '.zst':
                data = subprocess.check_output(['zstd', '-dc', str(source)])
            (initrd_root / name).write_bytes(data)
            driver_commands.append(f'insmod /{name} || {{ echo GLF_DRIVER_FAILED; poweroff -f; }}')
        driver_commands.append(f'echo GLF_DRIVER_OK_{driver}')
    for app in ("sh", "mount", "umount", "insmod", "rmmod", "mkdir", "cat", "od", "sleep", "poweroff"):
        (initrd_root / "bin" / app).symlink_to("busybox")
    (initrd_root / "init").write_text('''#!/bin/sh
export PATH=/bin
mkdir -p /proc /sys /dev
mount -t proc proc /proc
mount -t sysfs sysfs /sys
mount -t devtmpfs devtmpfs /dev
mount -t securityfs securityfs /sys/kernel/security
insmod /efivarfs.ko || { echo GLF_MODULE_LOAD_FAILED; poweroff -f; }
mount -t efivarfs efivarfs /sys/firmware/efi/efivars
printf 'GLF_SECURE_BOOT='
cat /sys/firmware/efi/efivars/SecureBoot-* | od -An -t u1 -j4 -N1
umount /sys/firmware/efi/efivars
rmmod efivarfs || { echo GLF_MODULE_UNLOAD_FAILED; poweroff -f; }
if insmod /corrupt.ko; then
    echo GLF_CORRUPTED_MODULE_ACCEPTED
else
    echo GLF_CORRUPTED_MODULE_REJECTED
fi
printf 'GLF_LOCKDOWN='
cat /sys/kernel/security/lockdown
printf 'GLF_CMDLINE='
cat /proc/cmdline
__DRIVER_COMMANDS__
echo GLF_UEFI_BOOT_OK
sleep 1
poweroff -f
'''.replace('__DRIVER_COMMANDS__', '\n'.join(driver_commands)))
    (initrd_root / "init").chmod(0o755)
    files = ["."] + [str(p.relative_to(initrd_root)) for p in initrd_root.rglob("*")]
    archive = subprocess.check_output(["cpio", "-o", "-H", "newc"], input=("\n".join(files) + "\n").encode(), cwd=initrd_root)
    initrd = root / "initrd"
    initrd.write_bytes(archive)
    esp = root / "esp"
    (esp / "EFI/BOOT").mkdir(parents=True)
    (esp / "EFI/Linux").mkdir()
    (esp / "loader").mkdir()
    (esp / "loader/loader.conf").write_text("default glf-test.efi\ntimeout 0\neditor no\n")
    shutil.copyfile(Path(os.environ["GLF_TEST_SHIM"]) / "shimx64.efi", esp / "EFI/BOOT/BOOTX64.EFI")
    shutil.copyfile(Path(os.environ["GLF_TEST_SHIM"]) / "mmx64.efi", esp / "EFI/BOOT/mmx64.efi")
    run("sbsign", "--key", key, "--cert", cert, "--output", esp / "EFI/BOOT/grubx64.efi", os.environ["GLF_TEST_BOOT"])
    osrelease = root / "os-release"
    osrelease.write_text('ID=glf-test\nPRETTY_NAME="GLF VM TEST"\nVERSION_ID=1\n')
    uki = root / "unsigned.efi"
    run(os.environ["GLF_TEST_UKIFY"], "build", "--linux", kernel, "--initrd", initrd,
        "--stub", os.environ["GLF_TEST_STUB"], "--os-release", "@" + str(osrelease),
        "--cmdline", "console=ttyS0 rdinit=/init module.sig_enforce=1 lockdown=integrity", "--output", uki)
    run("sbsign", "--key", key, "--cert", cert, "--output", esp / "EFI/Linux/glf-test.efi", uki)
    firmware = Path(os.environ["GLF_VM_FIRMWARE"])
    varstore = root / "vars.fd"
    run("virt-fw-vars", "--input", firmware / "OVMF_VARS.fd", "--output", varstore,
        "--enroll-generate", "GLF VM PLATFORM", "--microsoft-db", "all", "--sb",
        "--add-mok", "605dab50-e046-4300-abb6-3dd810dd8b23", cert)
    disk = root / "esp.img"
    with disk.open("wb") as stream:
        stream.truncate(128 * 1024 * 1024)
    run("mkfs.vfat", disk, stdout=subprocess.DEVNULL)
    for path in esp.iterdir():
        run("mcopy", "-i", disk, "-s", path, "::/")
    log = root / "serial.log"
    command = ["qemu-system-x86_64", "-machine", "q35,smm=on", "-accel", "tcg", "-cpu", "max", "-m", "1024",
               "-global", "driver=cfi.pflash01,property=secure,value=on",
               "-drive", f"if=pflash,format=raw,unit=0,readonly=on,file={firmware / 'OVMF_CODE.fd'}",
               "-drive", f"if=pflash,format=raw,unit=1,file={varstore}",
               "-drive", f"format=raw,file={disk}", "-display", "none", "-serial", f"file:{log}",
               "-monitor", "none", "-nic", "none", "-no-reboot"]
    try:
        run(*command, timeout=180)
    finally:
        text = log.read_text(errors="replace") if log.exists() else ""
        Path("dist").mkdir(exist_ok=True)
        Path("dist/uefi-serial.log").write_text(text)
    assert "GLF_UEFI_BOOT_OK" in text, "Le noyau n'a pas atteint /init : voir dist/uefi-serial.log"
    assert "[integrity]" in text, "Lockdown integrity absent"
    for driver in ('hid-fanatec', 'hid-logitech-new'):
        assert f'GLF_DRIVER_OK_{driver}' in text, f'Module {driver} non charge'
    assert "GLF_CORRUPTED_MODULE_REJECTED" in text, "Module corrompu non rejete"
    assert "Key was rejected" in text, "Rejet de signature non confirme"
    secure_line = next(line for line in text.splitlines() if "GLF_SECURE_BOOT=" in line)
    assert secure_line.split("=")[-1].strip() == "1", "Secure Boot non actif"
    print("OK : UEFI Secure Boot -> shim Rocky -> systemd-boot signe MOK -> UKI -> noyau, lockdown integrity actif.")
