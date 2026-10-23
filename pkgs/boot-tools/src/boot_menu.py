"""Libelle des generations locales pour les entrees systemd-boot."""
import datetime
import json
from pathlib import Path
import re
import shlex


def menu_header(target, profiles=Path("/nix/var/nix/profiles")):
    target = Path(target).resolve(strict=True)
    label = target.name
    bootspec = target / "boot.json"
    if bootspec.is_file():
        try:
            spec = json.loads(bootspec.read_text()).get("org.nixos.bootspec.v1", {})
            candidate = spec.get("label")
            if isinstance(candidate, str) and candidate.strip():
                label = candidate
        except (ValueError, AttributeError):
            pass  # Un ancien bootspec invalide ne doit pas bloquer le demarrage.
    # GLF remplace VERSION_CODENAME par son propre nom de version dans
    # os-release. Reconstruire le libelle evite tout nom de code NixOS,
    # sans retirer par erreur la version GLF (ex. Rising).
    release = target / "etc/os-release"
    if release.is_file():
        fields = {}
        for line in release.read_text().splitlines():
            key, sep, value = line.partition("=")
            if sep and key in ("ID", "VERSION_CODENAME"):
                try:
                    words = shlex.split(value, comments=True)
                except ValueError:
                    continue
                if len(words) == 1:
                    fields[key] = words[0]
        kernel = re.search(r"\(Linux [^()\r\n]+\)$", label)
        if fields.get("ID") == "glfos" and fields.get("VERSION_CODENAME") and kernel:
            label = f"GLF-OS {fields['VERSION_CODENAME']} {kernel[0]}"
    # Un libelle reste une seule ligne, jamais une directive de boot.
    label = " ".join(label.split())
    generations = []
    for link in Path(profiles).glob("system-*-link"):
        match = re.fullmatch(r"system-([0-9]+)-link", link.name)
        if not match or not link.is_symlink():
            continue
        try:
            if link.resolve(strict=True) == target:
                generations.append((int(match[1]), link.lstat().st_mtime))
        except FileNotFoundError:
            continue
    if generations:
        # Une meme fermeture peut avoir plusieurs numeros de generation.
        number, timestamp = max(generations)
        date = datetime.datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d")
        description = f"Generation {number} {label}, built on {date}"
    else:
        # Installation initiale ou profil supprime : ne pas inventer numero/date.
        description = label
    return f"title GLF-OS\nversion {description}\nsort-key glf-os\n"
