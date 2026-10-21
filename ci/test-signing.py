"""Test local avec une cle jetable et un stub PE, jamais avec la cle GLF."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

repo = Path(__file__).resolve().parent.parent
stub = Path(sys.argv[1]).resolve()


def run(args, *, env=None, ok=True):
    result = subprocess.run(args, env=env, capture_output=True, text=True)
    if (result.returncode == 0) != ok:
        raise AssertionError(f"Resultat inattendu pour {args[0]}: {result.returncode}")
    return result.stdout


with tempfile.TemporaryDirectory(prefix="glf-sign-test-") as temp:
    os.chdir(temp)
    unsigned = Path("dist/unsigned")
    unsigned.mkdir(parents=True)
    for name in ("kernel.efi", "glf-os.efi"):
        shutil.copyfile(stub, unsigned / name)
    (unsigned / "modules.cer").write_bytes(b"fixture-certificates")
    (unsigned / "bundle.sha256").write_text("fixture\n")
    (unsigned / "nix-closure.json").write_text("{}")
    (unsigned / "store-paths.txt").write_text("/nix/store/fixture\n")
    hashes = "".join(
        f"{hashlib.sha256((unsigned / name).read_bytes()).hexdigest()}  {name}\n"
        for name in ("kernel.efi", "glf-os.efi", "modules.cer", "bundle.sha256")
    )
    (unsigned / "SHA256SUMS").write_text(hashes)
    run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes",
         "-keyout", "key.pem", "-out", "cert.pem", "-subj", "/CN=GLF TEST ONLY/", "-days", "1"])
    fingerprint = run(["openssl", "x509", "-in", "cert.pem", "-noout", "-fingerprint", "-sha256"]).strip().split("=")[1]
    env = {k: v for k, v in os.environ.items() if not k.startswith("GLF_")}
    sign = ["bash", str(repo / "ci/sign.sh")]
    run(sign, env=env, ok=False)
    key = Path("key.pem").read_text()
    env.update(GLF_SIGNING_KEY_PEM=key, GLF_SIGNING_CERT_PEM=Path("cert.pem").read_text(), GLF_CERT_SHA256=fingerprint)
    run(sign, env={**env, "GLF_CERT_SHA256": "00" * 32}, ok=False)
    run(["openssl", "genpkey", "-algorithm", "RSA", "-pkeyopt", "rsa_keygen_bits:2048", "-out", "other.pem"])
    run(sign, env={**env, "GLF_SIGNING_KEY_PEM": Path("other.pem").read_text()}, ok=False)
    with (unsigned / "glf-os.efi").open("ab") as stream:
        stream.write(b"tampered")
    run(sign, env=env, ok=False)
    shutil.copyfile(stub, unsigned / "glf-os.efi")
    run(sign, env=env)
    run(["bash", str(repo / "ci/attic-mock.sh")])
    report = json.loads(Path("dist/attic-mock.json").read_text())
    assert report["mode"] == "mock" and report["uploaded"] is False
    for output in Path("dist").rglob("*"):
        if output.is_file():
            assert key.encode() not in output.read_bytes()
    print("OK: signature PE, refus secrets absents/empreinte/cle/artefact invalides, Attic simule sans cle.")
