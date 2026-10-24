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
        if args[0] == "nix":
            print(result.stderr, file=sys.stderr)
        raise AssertionError(f"Resultat inattendu pour {args[0]}: {result.returncode}")
    return result.stdout


with tempfile.TemporaryDirectory(prefix="glf-sign-test-") as temp:
    os.chdir(temp)
    unsigned = Path("dist/unsigned")
    unsigned.mkdir(parents=True)
    for name in ("kernel.efi", "refind_x64.efi", "systemd-bootx64.efi", "shimx64.efi", "mmx64.efi"):
        shutil.copyfile(stub, unsigned / name)
    (unsigned / "release.json").write_text(json.dumps({"commit": "a" * 40, "branch": "Rising", "profile": "current", "channels": {"commit": "b" * 40}}))
    (unsigned / "modules.cer").write_bytes(b"fixture-certificates")
    (unsigned / "bundle.sha256").write_text("fixture\n")
    (unsigned / "nix-closure.json").write_text("{}")
    (unsigned / "flake.lock").write_text('{"fixture": true}\n')
    # Include real store references: an unpacked fixed-output fetch must fail.
    (unsigned / "store-paths.txt").write_text(str(stub) + "\n")
    hashes = "".join(
        f"{hashlib.sha256((unsigned / name).read_bytes()).hexdigest()}  {name}\n"
        for name in ("kernel.efi", "refind_x64.efi", "systemd-bootx64.efi", "shimx64.efi", "mmx64.efi", "modules.cer", "bundle.sha256")
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
    with (unsigned / "kernel.efi").open("ab") as stream:
        stream.write(b"tampered")
    run(sign, env=env, ok=False)
    shutil.copyfile(stub, unsigned / "kernel.efi")
    run(sign, env=env)
    assert Path('dist/signed/shimx64.efi').read_bytes() == stub.read_bytes()
    assert Path('dist/signed/mmx64.efi').read_bytes() == stub.read_bytes()
    assert not Path('dist/signed/glf-os.efi').exists()
    run(['bash', str(repo / 'ci/package-release.sh')], env={**env, 'GITHUB_REPOSITORY': 'Xdavius/NIX_SB'})
    descriptor = json.loads(Path('dist/release/release.json').read_text())
    assert descriptor['hash'].startswith('sha256-')
    assert descriptor['version'] == 2
    assert descriptor['archiveHash'] == run(['nix', 'hash', 'file', 'dist/release/glf-secureboot.tar.gz']).strip()
    assert descriptor['commit'] == 'a' * 40
    Path('unpacked').mkdir()
    run(['tar', '-xzf', 'dist/release/glf-secureboot.tar.gz', '-C', 'unpacked'])
    assert Path('unpacked/flake.lock').read_bytes() == (unsigned / 'flake.lock').read_bytes()
    assert run(['nix', 'hash', 'path', 'unpacked']).strip() == descriptor['hash']
    # Build the actual package expression in an isolated tree with a disposable
    # trusted certificate. Production certificate files are never modified.
    fixture = Path('fixture')
    shutil.copytree(repo / 'pkgs/signed', fixture / 'pkgs/signed')
    (fixture / 'pkgs/boot-tools/src').mkdir(parents=True)
    shutil.copyfile(repo / 'pkgs/boot-tools/src/signing_protocol.py', fixture / 'pkgs/boot-tools/src/signing_protocol.py')
    (fixture / 'certificates/production').mkdir(parents=True)
    shutil.copyfile('dist/signed/GLF.pem', fixture / 'certificates/production/GLF.pem')
    shutil.copyfile('dist/signed/GLF.cer', fixture / 'certificates/production/GLF.cer')
    for directory in ('kernel', 'systemd/lib/systemd/boot/efi', 'shim/share/efi', 'refind/share/efi'):
        (fixture / directory).mkdir(parents=True)
    shutil.copyfile(stub, fixture / 'refind/share/efi/refind_x64.efi')
    shutil.copyfile(stub, fixture / 'kernel/bzImage')
    shutil.copyfile(stub, fixture / 'systemd/lib/systemd/boot/efi/systemd-bootx64.efi')
    for name in ('shimx64.efi', 'mmx64.efi'):
        shutil.copyfile(stub, fixture / 'shim/share/efi' / name)
    archive = run(['nix', 'store', 'add-file', str(Path('dist/release/glf-secureboot.tar.gz').resolve())]).strip()
    descriptor['url'] = 'file://' + archive
    (fixture / 'release.json').write_text(json.dumps(descriptor))
    shutil.copyfile('dist/release/glf-secureboot.tar.gz', fixture / 'archive.tar.gz')
    nixpkgs = json.dumps(os.environ['GLF_TEST_NIXPKGS'])
    (fixture / 'check.nix').write_text(f'''let
  pkgs = import (builtins.toPath {nixpkgs}) {{ system = "x86_64-linux"; }};
  signed = pkgs.callPackage ./pkgs/signed {{
    releaseFile = ./release.json;
    fetchurl = args: pkgs.fetchurl (args // {{ url = "file://${{./archive.tar.gz}}"; }});
    kernel = {{ outPath = builtins.path {{ path = ./kernel; }}; version = "fixture"; }};
    systemd = ./systemd;
    refind = ./refind;
    rockyShim = ./shim;
  }};
in signed.bundle
''')
    run(['nix', 'build', '--file', str(fixture / 'check.nix'), '--no-link'])
    run(["bash", str(repo / "ci/attic-mock.sh")])
    report = json.loads(Path("dist/attic-mock.json").read_text())
    assert report["mode"] == "mock" and report["uploaded"] is False
    for output in Path("dist").rglob("*"):
        if output.is_file():
            assert key.encode() not in output.read_bytes()
    print("OK: signature PE, refus secrets absents/empreinte/cle/artefact invalides, archive et import Nix valides, Attic simule sans cle.")
