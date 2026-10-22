"""Verification locale des empreintes et du contenu PE signe."""
import hashlib
from pathlib import Path
import struct


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


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
