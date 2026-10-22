#!/usr/bin/env python3
"""Install a verified shim -> systemd-boot -> machine-specific UKI generation."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from signing_protocol import digest, pe_content


def run(*args, **kwargs):
    return subprocess.run([str(x) for x in args], check=True, **kwargs)


def atomic_copy(source, destination):
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    # Do not follow a pre-existing temporary symlink on a non-FAT test filesystem.
    fd, tmp = tempfile.mkstemp(prefix=".glf-", dir=destination.parent)
    try:
        with os.fdopen(fd, "wb") as output, open(source, "rb") as source_file:
            shutil.copyfileobj(source_file, output)
            output.flush()
            os.fsync(output.fileno())
        os.chmod(tmp, 0o644)
        os.replace(tmp, destination)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def signer_command(config):
    signer = config.get("signerCommand")
    if (not isinstance(signer, list) or not signer
            or not all(isinstance(arg, str) and arg for arg in signer)):
        raise ValueError("signerCommand doit etre une liste non vide de chaines")
    return signer


def install(config, target, allow_unmounted=False):
    signer = signer_command(config)
    target = Path(target).resolve(strict=True)
    if not (target / "init").is_file():
        raise ValueError("Generation NixOS sans init")
    metadata = json.loads((target / "glf-secureboot.json").read_text())
    if metadata.get("version") != 1:
        raise ValueError("Generation incompatible avec le chargeur GLF")
    esp = Path(config["esp"])
    if not allow_unmounted:
        info = json.loads(subprocess.check_output(
            ["findmnt", "--json", "--mountpoint", str(esp), "--output", "TARGET,FSTYPE,SOURCE"], text=True))
        if info["filesystems"][0]["fstype"] != "vfat":
            raise ValueError("L'ESP doit etre une partition FAT montee")
    esp.mkdir(parents=True, exist_ok=True)
    identifier = hashlib.sha256(str(target).encode()).hexdigest()[:32]
    filename = f"glf-{identifier}.efi"
    # Lock serializes installations across signing waits; lock remains on the ESP.
    with open(esp / ".glf-install.lock", "a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        with tempfile.TemporaryDirectory(prefix="glf-install-") as temporary:
            work = Path(temporary)
            unsigned, signed = work / "unsigned", work / "signed"
            unsigned.mkdir()
            shutil.copyfile(metadata["kernel"], unsigned / "kernel.efi")
            shutil.copyfile(metadata["systemdBoot"], unsigned / "systemd-bootx64.efi")
            cmdline = " ".join([f"init={target}/init", *metadata["kernelParams"]])
            run(metadata["ukify"], "build", "--linux", metadata["kernel"],
                "--initrd", metadata["initrd"], "--stub", metadata["stub"],
                "--cmdline", cmdline, "--os-release", f"@{target}/etc/os-release",
                "--uname", metadata["kernelVersion"], "--output", unsigned / "glf-os.efi")
            # Le transport de signature est fourni par le consommateur.
            run(*signer, "--certificate", config["certificate"],
                "--system", str(target), unsigned, signed)
            # Verify again at the deployment boundary, even if the client already did.
            for name in ("kernel.efi", "glf-os.efi", "systemd-bootx64.efi"):
                run("sbverify", "--cert", config["certificate"], signed / name)
                if pe_content(unsigned / name) != pe_content(signed / name):
                    raise ValueError("Le signataire a modifie le contenu de " + name)
            shim = Path(config["shim"])
            # Stage/verify everything above BEFORE modifying bootable files.
            atomic_copy(signed / "glf-os.efi", esp / "EFI/Linux" / filename)
            for directory, shim_name in (("EFI/GLF", "shimx64.efi"), ("EFI/BOOT", "BOOTX64.EFI")):
                atomic_copy(shim / "mmx64.efi", esp / directory / "mmx64.efi")
                atomic_copy(signed / "systemd-bootx64.efi", esp / directory / "grubx64.efi")
                atomic_copy(shim / "shimx64.efi", esp / directory / shim_name)
            atomic_copy(signed / "systemd-bootx64.efi", esp / "EFI/systemd/systemd-bootx64.efi")
            atomic_copy(config["certificate"], esp / "EFI/GLF/GLF.pem")
            loader = work / "loader.conf"
            loader.write_text(f"default {filename}\ntimeout {config['timeout']}\neditor no\nauto-entries yes\nsecure-boot-enroll off\n")
            atomic_copy(loader, esp / "loader/loader.conf")
            # Record the exact generation for diagnostics and retention; never prune
            # someone else's entries or pre-existing OS files.
            record = work / "generation.json"
            record.write_text(json.dumps({"system": str(target), "sha256": digest(signed / "glf-os.efi")}))
            atomic_copy(record, esp / "EFI/GLF/generations" / (filename + ".json"))
            if config["canTouchEfiVariables"]:
                source = subprocess.check_output(["findmnt", "-n", "-o", "SOURCE", "--mountpoint", str(esp)], text=True).strip()
                block = json.loads(subprocess.check_output(["lsblk", "--json", "--output", "PKNAME,PARTN", source], text=True))["blockdevices"][0]
                if not block["pkname"] or not block["partn"]:
                    raise ValueError("Impossible de determiner le disque/partition ESP")
                entries = subprocess.check_output(["efibootmgr", "--verbose"], text=True)
                if "\\EFI\\GLF\\shimx64.efi".lower() not in entries.lower():
                    run("efibootmgr", "--create", "--disk", "/dev/" + block["pkname"], "--part", str(block["partn"]),
                        "--label", "GLF-OS shim", "--loader", "\\EFI\\GLF\\shimx64.efi")
                run("bootctl", "--esp-path=" + str(esp), "set-default", filename)
            # Old UKIs remain available for rollback; no automatic deletion here.
            print(f"Generation installee : {filename}. Chaine : shim Rocky -> systemd-boot -> UKI.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--allow-unmounted", action="store_true", help="Uniquement pour un dossier de test, sans ecriture NVRAM")
    parser.add_argument("target")
    args = parser.parse_args()
    config = json.loads(Path(args.config).read_text())
    if args.allow_unmounted and config["canTouchEfiVariables"]:
        parser.error("--allow-unmounted interdit avec ecriture des variables EFI")
    install(config, args.target, args.allow_unmounted)


if __name__ == "__main__":
    main()
