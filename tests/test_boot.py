"""Real PE signatures and UKI assembly, with a local disposable signing fixture.

No production key, GitHub call, mounted ESP or firmware variable is used.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
from install_boot import install
from signing_protocol import IMAGES, prepare, validate, verify_response


class BootTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="glf-boot-test-")
        cls.root = Path(cls.tmp.name)
        cls.key = cls.root / "key.pem"
        cls.cert = cls.root / "cert.pem"
        subprocess.run(["openssl", "req", "-newkey", "rsa:2048", "-nodes", "-x509", "-days", "1",
                        "-subj", "/CN=GLF DISPOSABLE TEST/", "-keyout", str(cls.key), "-out", str(cls.cert)],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        cls.signer = cls.root / "signer"
        cls.signer.write_text(f'''#!{sys.executable}
import pathlib, subprocess, sys
source, dest = map(pathlib.Path, sys.argv[-2:])
dest.mkdir()
for name in {IMAGES!r}:
    subprocess.run(['sbsign', '--key', {str(cls.key)!r}, '--cert', {str(cls.cert)!r}, '--output', str(dest/name), str(source/name)], check=True)
''')
        cls.signer.chmod(0o700)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def target(self, name):
        target = self.root / name
        target.mkdir()
        (target / "init").write_text("fixture")
        (target / "etc").mkdir()
        (target / "etc/os-release").write_text('ID=glf-test\nPRETTY_NAME="GLF TEST"\nVERSION_ID=1\n')
        initrd = target / "initrd"
        initrd.write_bytes(b"fixture initrd")
        metadata = {
            "version": 1, "kernel": os.environ["GLF_TEST_STUB"], "stub": os.environ["GLF_TEST_STUB"],
            "initrd": str(initrd), "systemdBoot": os.environ["GLF_TEST_BOOT"],
            "ukify": os.environ["GLF_TEST_UKIFY"], "kernelVersion": "test",
            "kernelParams": ["root=LABEL=machine-specific", "lockdown=integrity", "module.sig_enforce=1"],
        }
        (target / "glf-boot.json").write_text(json.dumps(metadata))
        return target

    def config(self, name):
        return {"esp": str(self.root / name), "certificate": str(self.cert),
                "shim": os.environ["GLF_TEST_SHIM"], "githubSigner": str(self.signer),
                "repository": "fixture/fixture", "ref": "main", "signingTimeout": 60,
                "timeout": "5", "canTouchEfiVariables": False}

    def test_install_and_rollback(self):
        config = self.config("esp")
        first, second = self.target("first"), self.target("second")
        install(config, first, allow_unmounted=True)
        install(config, second, allow_unmounted=True)
        esp = Path(config["esp"])
        self.assertEqual(len(list((esp / "EFI/Linux").glob("glf-*.efi"))), 2)
        self.assertEqual((esp / "EFI/BOOT/BOOTX64.EFI").read_bytes(), (Path(config["shim"]) / "shimx64.efi").read_bytes())
        self.assertEqual((esp / "EFI/GLF/grubx64.efi").read_bytes(), (esp / "EFI/systemd/systemd-bootx64.efi").read_bytes())
        install(config, first, allow_unmounted=True)
        first_name = "glf-" + hashlib.sha256(str(first).encode()).hexdigest()[:32] + ".efi"
        self.assertIn(first_name, (esp / "loader/loader.conf").read_text())
        dumped = self.root / "cmdline"
        subprocess.run(["objcopy", "--dump-section", f".cmdline={dumped}", str(esp / "EFI/Linux" / first_name), str(self.root / "copy.efi")], check=True)
        self.assertIn(f"init={first}/init", dumped.read_text())
        self.assertIn("root=LABEL=machine-specific", dumped.read_text())

    def test_signing_failure_preserves_esp(self):
        config = self.config("failure-esp")
        esp = Path(config["esp"])
        (esp / "loader").mkdir(parents=True)
        (esp / "loader/loader.conf").write_text("old default")
        config["githubSigner"] = "/does-not-exist"
        with self.assertRaises(FileNotFoundError):
            install(config, self.target("failure"), allow_unmounted=True)
        self.assertEqual((esp / "loader/loader.conf").read_text(), "old default")
        self.assertFalse((esp / "EFI").exists())

    def test_protocol_and_payload(self):
        unsigned, signed = self.root / "input", self.root / "signed"
        unsigned.mkdir()
        for name in IMAGES:
            shutil.copyfile(os.environ["GLF_TEST_STUB"], unsigned / name)
        expected = prepare(unsigned, "fixture")
        validate(unsigned, expected)
        with self.assertRaises(ValueError):
            validate(unsigned, "0" * 64)
        subprocess.run([str(self.signer), str(unsigned), str(signed)], check=True)
        verify_response(unsigned, signed, self.cert)
        # An authentic signature of a DIFFERENT payload must still be rejected.
        shutil.copyfile(os.environ["GLF_TEST_BOOT"], unsigned / "kernel.efi")
        with self.assertRaises(ValueError):
            verify_response(unsigned, signed, self.cert)
        with self.assertRaises(ValueError):
            validate(unsigned, expected)


if __name__ == "__main__":
    unittest.main()
