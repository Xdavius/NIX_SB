"""The signer independently enforces the reviewed kernel, loader and UKI stub."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'pkgs' / 'boot-tools' / 'src'))
from signing_policy import validate_policy, section


class PolicyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.kernel = Path(os.environ['GLF_TEST_STUB'])
        self.boot = Path(os.environ['GLF_TEST_BOOT'])
        self.ukify = os.environ['GLF_TEST_UKIFY']
        shutil.copyfile(self.kernel, self.root / 'kernel.efi')
        shutil.copyfile(self.boot, self.root / 'systemd-bootx64.efi')
        (self.root / 'initrd').write_bytes(b'initrd fixture')
        (self.root / 'osrel').write_text('ID=test\nPRETTY_NAME="TEST"\n')

    def build(self, params='module.sig_enforce=1 lockdown=integrity', kernel=None):
        subprocess.run([self.ukify, 'build', '--linux', str(kernel or self.kernel),
                        '--stub', str(self.kernel), '--initrd', str(self.root / 'initrd'),
                        '--os-release', '@' + str(self.root / 'osrel'), '--uname', 'test',
                        '--cmdline', params, '--output', str(self.root / 'glf-os.efi')], check=True)

    def validate(self):
        validate_policy(self.root, self.kernel, self.boot, self.kernel, self.ukify)

    def test_canonical_machine_uki(self):
        self.build('init=/nix/store/machine/init root=LABEL=custom module.sig_enforce=1 lockdown=integrity')
        self.validate()

    def test_unapproved_kernel_and_loader(self):
        self.build()
        for name in ('kernel.efi', 'systemd-bootx64.efi'):
            original = (self.root / name).read_bytes()
            (self.root / name).write_bytes(original + b'changed')
            with self.assertRaises(ValueError):
                self.validate()
            (self.root / name).write_bytes(original)

    def test_different_embedded_kernel(self):
        self.build(kernel=self.boot)
        with self.assertRaisesRegex(ValueError, 'embarque'):
            self.validate()

    def test_modified_stub(self):
        self.build()
        text = bytearray(section(self.root / 'glf-os.efi', '.text'))
        text[0] ^= 1
        (self.root / 'text').write_bytes(text)
        subprocess.run(['objcopy', '--update-section', '.text=' + str(self.root / 'text'),
                        str(self.root / 'glf-os.efi')], check=True)
        with self.assertRaisesRegex(ValueError, 'non canonique'):
            self.validate()

    def test_weakened_params(self):
        for params in ('module.sig_enforce=0 lockdown=integrity',
                       'module.sig_enforce=1 lockdown=none',
                       'module.sig_enforce=1 lockdown=integrity module.sig_enforce=0',
                       '-- module.sig_enforce=1 lockdown=integrity'):
            with self.subTest(params=params):
                self.build(params)
                with self.assertRaises(ValueError):
                    self.validate()


if __name__ == '__main__':
    unittest.main()
