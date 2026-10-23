#!/usr/bin/env python3
"""Install a verified shim -> systemd-boot -> signed kernel with a separate local initrd."""
from boot_menu import menu_header

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


def install(config, target, allow_unmounted=False):
    if "signerCommand" in config:
        raise ValueError("signerCommand retire : fournir signedBundle dans les metadonnees v2")
    target = Path(target).resolve(strict=True)
    if not (target / "init").is_file():
        raise ValueError("Generation NixOS sans init")
    metadata = json.loads((target / "glf-secureboot.json").read_text())
    if metadata.get("version") != 2:
        raise ValueError("Metadonnees v2 requises : noyau signe et initrd separe")
    bundle = Path(metadata["signedBundle"])
    params = metadata["kernelParams"]
    if (not isinstance(params, list) or
            not all(isinstance(p, str) and p and not any(c in p for c in "\n\r\0") for p in params)):
        raise ValueError("Parametres noyau invalides")
    import shlex
    tokens = shlex.split(" ".join(params))
    for key, expected in (("module.sig_enforce", "1"), ("lockdown", "integrity")):
        matches = [p for p in tokens if p.split("=", 1)[0].replace("-", "_") == key.replace("-", "_")]
        if matches != [f"{key}={expected}"] or "--" in tokens:
            raise ValueError("Politique noyau invalide : " + key)
    if any(p.split("=", 1)[0] == "init" for p in tokens):
        raise ValueError("init est fourni par l'installateur")
    timeout = str(config["timeout"])
    if not timeout.isdecimal():
        raise ValueError("timeout doit etre un entier positif ou nul")
    # No network or signing operation: only already-published components.
    for name in ("kernel.efi", "systemd-bootx64.efi"):
        run("sbverify", "--cert", config["certificate"], bundle / name)
    if pe_content(metadata["kernel"]) != pe_content(bundle / "kernel.efi"):
        raise ValueError("Le noyau signe ne correspond pas a cette generation")
    initrd = Path(metadata["initrd"])
    if not initrd.is_file():
        raise ValueError("Initrd local absent")
    for name in ("shimx64.efi", "mmx64.efi"):
        if not (bundle / name).is_file():
            raise ValueError("Publication incomplete : " + name)
    esp = Path(config["esp"])
    if not allow_unmounted:
        info = json.loads(subprocess.check_output(
            ["findmnt", "--json", "--mountpoint", str(esp), "--output", "TARGET,FSTYPE,SOURCE"], text=True))
        if info["filesystems"][0]["fstype"] != "vfat":
            raise ValueError("L'ESP doit etre une partition FAT montee")
    esp.mkdir(parents=True, exist_ok=True)
    identifier = hashlib.sha256(str(target).encode()).hexdigest()[:32]
    entry = f"glf-{identifier}.conf"
    directory = f"EFI/GLF/generations/{identifier}"
    with open(esp / ".glf-install.lock", "a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        with tempfile.TemporaryDirectory(prefix="glf-install-") as temporary:
            work = Path(temporary)
            atomic_copy(bundle / "kernel.efi", esp / directory / "kernel.efi")
            atomic_copy(initrd, esp / directory / "initrd")
            for bootdir, shim_name in (("EFI/GLF", "shimx64.efi"), ("EFI/BOOT", "BOOTX64.EFI")):
                atomic_copy(bundle / "mmx64.efi", esp / bootdir / "mmx64.efi")
                atomic_copy(bundle / "systemd-bootx64.efi", esp / bootdir / "grubx64.efi")
                atomic_copy(bundle / "shimx64.efi", esp / bootdir / shim_name)
            atomic_copy(bundle / "systemd-bootx64.efi", esp / "EFI/systemd/systemd-bootx64.efi")
            atomic_copy(config["certificate"], esp / "EFI/GLF/GLF.pem")
            cmdline = " ".join([f"init={target}/init", *params])
            boot_entry = work / "entry.conf"
            boot_entry.write_text(menu_header(target) + f"linux /{directory}/kernel.efi\n"
                                  f"initrd /{directory}/initrd\noptions {cmdline}\n")
            atomic_copy(boot_entry, esp / "loader/entries" / entry)
            record = work / "generation.json"
            record.write_text(json.dumps({"system": str(target), "bundle": str(bundle),
                                          "kernelSha256": digest(bundle / "kernel.efi"),
                                          "initrdSha256": digest(initrd)}))
            atomic_copy(record, esp / directory / "generation.json")
            loader = work / "loader.conf"
            loader.write_text(f"default {entry}\ntimeout {timeout}\neditor no\nauto-entries yes\nsecure-boot-enroll off\n")
            atomic_copy(loader, esp / "loader/loader.conf")
            if config["canTouchEfiVariables"]:
                source = subprocess.check_output(["findmnt", "-n", "-o", "SOURCE", "--mountpoint", str(esp)], text=True).strip()
                block = json.loads(subprocess.check_output(["lsblk", "--json", "--output", "PKNAME,PARTN", source], text=True))["blockdevices"][0]
                if not block["pkname"] or not block["partn"]:
                    raise ValueError("Impossible de determiner le disque/partition ESP")
                entries = subprocess.check_output(["efibootmgr", "--verbose"], text=True)
                if "\\EFI\\GLF\\shimx64.efi".lower() not in entries.lower():
                    run("efibootmgr", "--create", "--disk", "/dev/" + block["pkname"], "--part", str(block["partn"]),
                        "--label", "GLF-OS shim", "--loader", "\\EFI\\GLF\\shimx64.efi")
                run("bootctl", "--esp-path=" + str(esp), "set-default", entry)
            print(f"Generation installee : {entry}. Noyau signe et initrd local separe.")


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
