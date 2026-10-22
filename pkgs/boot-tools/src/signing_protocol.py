"""Public file protocol shared by the client and an external signing service."""
import hashlib
import json
from pathlib import Path
import re
import struct
import subprocess

IMAGES = ("kernel.efi", "glf-os.efi", "systemd-bootx64.efi")


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def prepare(directory, system):
    directory = Path(directory)
    manifest = {"version": 1, "system": system,
                "files": {name: digest(directory / name) for name in IMAGES}}
    (directory / "request.json").write_text(json.dumps(manifest, sort_keys=True) + "\n")
    return digest(directory / "request.json")


def validate(directory, expected):
    directory = Path(directory)
    if not re.fullmatch(r"[a-f0-9]{64}", expected) or digest(directory / "request.json") != expected:
        raise ValueError("Empreinte de demande incorrecte")
    manifest = json.loads((directory / "request.json").read_text())
    if manifest.get("version") != 1 or set(manifest.get("files", {})) != set(IMAGES):
        raise ValueError("Format de demande incorrect")
    for name in IMAGES:
        if digest(directory / name) != manifest["files"][name]:
            raise ValueError(f"Contenu modifie : {name}")
        pe_content(directory / name)
    (directory / "SHA256SUMS").write_text("".join(
        f"{manifest['files'][name]}  {name}\n" for name in IMAGES))


def pe_content(path):
    """Compare all bytes except PE checksum, certificate directory and certificate.

    Only certificates at EOF and zero alignment padding are accepted. This is
    intentionally narrower than a generic Authenticode parser.
    """
    data = bytearray(Path(path).read_bytes())
    if len(data) < 64 or data[:2] != b"MZ":
        raise ValueError("Image non PE")
    pe = struct.unpack_from("<I", data, 60)[0]
    if data[pe:pe + 4] != b"PE\0\0":
        raise ValueError("Signature PE absente")
    opt = pe + 24
    if struct.unpack_from("<H", data, opt)[0] != 0x20B:
        raise ValueError("Seul PE32+ x86_64 est accepte")
    if struct.unpack_from("<H", data, pe + 4)[0] != 0x8664:
        raise ValueError("Architecture PE incorrecte")
    security = opt + 112 + 8 * 4
    offset, size = struct.unpack_from("<II", data, security)
    if offset or size:
        if not size or offset < security + 8 or offset + size != len(data):
            raise ValueError("Table de certificats PE non supportee")
        del data[offset:]
    data[opt + 64:opt + 68] = bytes(4)
    data[security:security + 8] = bytes(8)
    return bytes(data).rstrip(b"\0")


def verify_response(unsigned, signed, certificate):
    unsigned, signed = Path(unsigned), Path(signed)
    for name in IMAGES:
        subprocess.run(["sbverify", "--cert", str(certificate), str(signed / name)], check=True)
        if pe_content(unsigned / name) != pe_content(signed / name):
            raise ValueError(f"Le service a change le contenu de {name}")
