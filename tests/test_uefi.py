"""Boot the real kernel via Rocky shim and systemd-boot, or experimental rEFInd.

Uses emulated firmware and an ephemeral MOK, never host EFI variables or GLF's key.
"""
import os
import json
import lzma
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


def run(*args, **kw):
    return subprocess.run([str(x) for x in args], check=True, **kw)


kernel = Path(sys.argv[1]).resolve(strict=True)
boot_mode = os.environ.get("GLF_VM_BOOT_MODE", "uki")
if boot_mode not in ("uki", "split"):
    raise ValueError("GLF_VM_BOOT_MODE: uki ou split attendu")
refind = os.environ.get("GLF_VM_REFIND")
if refind and boot_mode != "split":
    raise ValueError("rEFInd experiment requires split mode")
reject_kernel = os.environ.get("GLF_VM_CORRUPT_KERNEL", "0") == "1"
if reject_kernel and boot_mode != "split":
    raise ValueError("GLF_VM_CORRUPT_KERNEL exige le mode split")
variant = os.environ.get("GLF_VM_VARIANT", "catalogue")
if variant not in ("catalogue", "xone", "xonedo"):
    raise ValueError("GLF_VM_VARIANT: catalogue, xone ou xonedo attendu")
modules = os.environ["GLF_VM_MODULES" if variant == "catalogue" else "GLF_VM_MODULES_" + variant.upper()]
drivers = ('hid-fanatec', 'hid-logitech-new')
if variant != "catalogue":
    drivers += ('hid_tmff_new', 'hid_xpadneo', 'v4l2loopback', 'xone_dongle', 'xone_gip_gamepad')

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
    module = next(Path(modules).glob("lib/modules/*/kernel/fs/efivarfs/efivarfs.ko*"))
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
    for driver in drivers:
        version = next((Path(modules) / 'lib/modules').iterdir()).name
        deps = subprocess.check_output(['modprobe', '--show-depends', '-d', modules,
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
    entry = "glf-test.conf" if boot_mode == "split" else "glf-test.efi"
    (esp / "loader/loader.conf").write_text(f"default {entry}\ntimeout 0\neditor no\n")
    shutil.copyfile(Path(os.environ["GLF_TEST_SHIM"]) / "shimx64.efi", esp / "EFI/BOOT/BOOTX64.EFI")
    shutil.copyfile(Path(os.environ["GLF_TEST_SHIM"]) / "mmx64.efi", esp / "EFI/BOOT/mmx64.efi")
    run("sbsign", "--key", key, "--cert", cert, "--output", esp / "EFI/BOOT/grubx64.efi", refind or os.environ["GLF_TEST_BOOT"])
    cmdline = "console=ttyS0 rdinit=/init module.sig_enforce=1 lockdown=integrity"
    if boot_mode == "split":
        (esp / "EFI/GLF").mkdir()
        (esp / "loader/entries").mkdir()
        run("sbsign", "--key", key, "--cert", cert,
            "--output", esp / "EFI/GLF/kernel.efi", kernel)
        if reject_kernel:
            signed_kernel = esp / "EFI/GLF/kernel.efi"
            data = bytearray(signed_kernel.read_bytes())
            # Reserved DOS-header byte, covered by Authenticode, outside EFI code.
            data[0x20] ^= 1
            signed_kernel.write_bytes(data)
            verification = subprocess.run(["sbverify", "--cert", str(cert), str(signed_kernel)],
                                          capture_output=True)
            assert verification.returncode != 0, "La signature alteree est encore valide"
        shutil.copyfile(initrd, esp / "EFI/GLF/initrd")
        (esp / "loader/entries/glf-test.conf").write_text(
            "title GLF separate initrd test\nlinux /EFI/GLF/kernel.efi\n"
            "initrd /EFI/GLF/initrd\noptions " + cmdline + "\n")
    else:
        osrelease = root / "os-release"
        osrelease.write_text('ID=glf-test\nPRETTY_NAME="GLF VM TEST"\nVERSION_ID=1\n')
        uki = root / "unsigned.efi"
        run(os.environ["GLF_TEST_UKIFY"], "build", "--linux", kernel, "--initrd", initrd,
            "--stub", os.environ["GLF_TEST_STUB"], "--os-release", "@" + str(osrelease),
            "--cmdline", cmdline, "--output", uki)
        run("sbsign", "--key", key, "--cert", cert, "--output", esp / "EFI/Linux/glf-test.efi", uki)
    if refind:
        assets = Path(__file__).resolve().parents[1] / "pkgs/multiboot-assets/assets"
        shutil.copytree(assets, esp / "EFI/BOOT/themes/glfos")
        icons = Path(refind).parents[1] / "refind/icons"
        shutil.copytree(icons, esp / "EFI/BOOT/icons")
        (esp / "EFI/BOOT/refind.conf").write_text(f"""timeout {0}
resolution 1024 768
scanfor manual
scan_all_linux_kernels false
use_nvram false
showtools
banner themes/glfos/glf-bootloader.png
banner_scale fillscreen
menuentry "GLF-OS" {{
    icon /EFI/BOOT/themes/glfos/glfos-logo.png
    loader /EFI/GLF/kernel.efi
    initrd /EFI/GLF/initrd
    options "{cmdline} glf_generation=default"
    submenu_on_select true
    submenuentry "Generation 42 - Rising - actuelle" {{
        options "{cmdline} glf_generation=42"
    }}
    submenuentry "Generation 41 - Rising - precedente" {{
        options "{cmdline} glf_generation=41"
    }}
}}
menuentry "Autre Linux (temoin sans sous-menu automatique)" {{
    icon /EFI/BOOT/icons/os_linux.png
    loader /EFI/GLF/kernel.efi
    initrd /EFI/GLF/initrd
    options "{cmdline} glf_generation=other"
}}
""")
    if os.environ.get('GLF_VM_INSTALLER'):
        if not refind or reject_kernel:
            raise ValueError('Le test installateur VM exige rEFInd et un noyau valide')
        bundle = root / 'published-bundle'
        bundle.mkdir()
        for source, name in ((esp / 'EFI/GLF/kernel.efi', 'kernel.efi'),
                             (esp / 'EFI/BOOT/grubx64.efi', 'refind_x64.efi'),
                             (esp / 'EFI/BOOT/BOOTX64.EFI', 'shimx64.efi'),
                             (esp / 'EFI/BOOT/mmx64.efi', 'mmx64.efi')):
            shutil.copyfile(source, bundle / name)
        run('sbsign', '--key', key, '--cert', cert, '--output', bundle / 'systemd-bootx64.efi',
            os.environ['GLF_TEST_BOOT'])
        esp = root / 'installed-esp'
        config_file = root / 'install.json'
        config_file.write_text(json.dumps({
            'esp': str(esp), 'certificate': str(cert),
            'timeout': '0',
            'canTouchEfiVariables': False, 'installFallback': True,
            'multiboot': {'enable': True, 'configurationLimit': 10},
        }))
        for number in (41, 42):
            generation = root / f'generation-{number}'
            generation.mkdir()
            (generation / 'init').write_text('fixture: initrd utilise rdinit=/init')
            (generation / 'boot.json').write_text(json.dumps({
                'org.nixos.bootspec.v1': {'label': f'Generation {number} - GLF-OS Rising'},
            }))
            (generation / 'glf-secureboot.json').write_text(json.dumps({
                'version': 2, 'signedBundle': str(bundle), 'kernel': str(kernel),
                'initrd': str(initrd), 'kernelParams': cmdline.split() + [f'glf_generation={number}'],
            }))
            run(os.environ['GLF_VM_INSTALLER'], '--allow-unmounted', '--config', config_file, generation)
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
    command = [os.environ.get("GLF_VM_QEMU", "qemu-system-x86_64"), "-machine", "q35,smm=on", "-accel", "tcg", "-cpu", "max", "-m", "1024",
               "-global", "driver=cfi.pflash01,property=secure,value=on",
               "-drive", f"if=pflash,format=raw,unit=0,readonly=on,file={firmware / 'OVMF_CODE.fd'}",
               "-drive", f"if=pflash,format=raw,unit=1,file={varstore}",
               "-drive", f"format=raw,file={disk}", "-display", "none", "-serial", f"file:{log}",
               "-monitor", "none", "-nic", "none", "-no-reboot"]
    if os.environ.get("GLF_VM_INTERACTIVE") == "1":
        command[command.index("-display") + 1] = "gtk"
        command += ["-name", "GLF-OS — aperçu multiboot"]
        print("VM interactive : Entrée ouvre les générations, Échap revient. Fermer la fenêtre pour quitter.", flush=True)
        run(*command)
        sys.exit(0)
    try:
        if refind:
            from refind_menu_vm import exercise_menu
            exercise_menu(command, root)
        else:
            run(*command, timeout=60 if reject_kernel else 180)
    except subprocess.TimeoutExpired:
        if not reject_kernel:
            raise
    finally:
        text = log.read_text(errors="replace") if log.exists() else ""
        Path("dist").mkdir(exist_ok=True)
        suffix = "-refind" if refind else "" if boot_mode == "uki" else "-split"
        if refind and os.environ.get("GLF_VM_REFIND_CHOICE") == "other":
            suffix += "-other"
        if reject_kernel:
            suffix += "-rejected"
        Path(f"dist/uefi-{variant}{suffix}-serial.log").write_text(text)
    if reject_kernel:
        assert "Linux version" not in text and "GLF_UEFI_BOOT_OK" not in text, "Noyau altere execute"
        assert "Security Violation" in text, "Rejet Secure Boot non observe dans le journal"
        print("OK : noyau altere refuse par la chaine shim / systemd-boot (Security Violation).")
        sys.exit(0)
    assert "GLF_UEFI_BOOT_OK" in text, "Le noyau n'a pas atteint /init : voir dist/uefi-<variante>-serial.log"
    assert "[integrity]" in text, "Lockdown integrity absent"
    for driver in drivers:
        assert f'GLF_DRIVER_OK_{driver}' in text, f'Module {driver} non charge'
    assert "GLF_CORRUPTED_MODULE_REJECTED" in text, "Module corrompu non rejete"
    assert "Key was rejected" in text, "Rejet de signature non confirme"
    secure_line = next(line for line in text.splitlines() if "GLF_SECURE_BOOT=" in line)
    assert secure_line.split("=")[-1].strip() == "1", "Secure Boot non actif"
    if refind:
        expected = "other" if os.environ.get("GLF_VM_REFIND_CHOICE") == "other" else "41"
        assert f"glf_generation={expected}" in text, "L'entree attendue n'a pas ete selectionnee"
        print(f"OK : entree {expected} demarree via rEFInd (navigation QMP).")
    payload = "noyau signe + initrd separe" if boot_mode == "split" else "UKI -> noyau"
    loader = "rEFInd" if refind else "systemd-boot"
    print(f"OK : UEFI Secure Boot -> shim Rocky -> {loader} signe MOK -> {payload}, lockdown integrity actif.")
