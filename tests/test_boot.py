"""Signatures reelles avec cle jetable ; aucune ecriture EFI sur l'hote."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'pkgs/boot-tools/src'))
from install_boot import install


class BootTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='glf-split-test-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.key, self.cert = self.root / 'key.pem', self.root / 'cert.pem'
        subprocess.run(['openssl', 'req', '-newkey', 'rsa:2048', '-nodes', '-x509', '-days', '1',
                        '-subj', '/CN=GLF DISPOSABLE TEST/', '-keyout', str(self.key), '-out', str(self.cert)],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.bundle = self.root / 'bundle'
        self.bundle.mkdir()
        for name, source in [('kernel.efi', 'GLF_TEST_STUB'), ('systemd-bootx64.efi', 'GLF_TEST_BOOT')]:
            subprocess.run(['sbsign', '--key', str(self.key), '--cert', str(self.cert),
                            '--output', str(self.bundle / name), os.environ[source]], check=True)
        for name in ('shimx64.efi', 'mmx64.efi'):
            shutil.copyfile(Path(os.environ['GLF_TEST_SHIM']) / name, self.bundle / name)
        self.esp = self.root / 'esp'
        self.config = {'esp': str(self.esp), 'certificate': str(self.cert),
                       'timeout': '5', 'canTouchEfiVariables': False}

    def target(self, name):
        target = self.root / name
        target.mkdir()
        (target / 'init').write_text('fixture')
        (target / 'initrd').write_bytes(b'local initrd ' + name.encode())
        (target / 'glf-secureboot.json').write_text(json.dumps({
            'version': 2, 'signedBundle': str(self.bundle), 'kernel': os.environ['GLF_TEST_STUB'],
            'initrd': str(target / 'initrd'),
            'kernelParams': ['root=LABEL=machine-specific', 'lockdown=integrity', 'module.sig_enforce=1'],
        }))
        return target

    def test_install_and_rollback(self):
        first, second = self.target('first'), self.target('second')
        for target in (first, second, first):
            install(self.config, target, allow_unmounted=True)
        identifier = hashlib.sha256(str(first).encode()).hexdigest()[:32]
        entry = f'glf-{identifier}.conf'
        self.assertEqual(len(list((self.esp / 'loader/entries').glob('*.conf'))), 2)
        self.assertIn(entry, (self.esp / 'loader/loader.conf').read_text())
        contents = (self.esp / 'loader/entries' / entry).read_text()
        self.assertIn('title GLF-OS\nversion first\nsort-key glf-os\n', contents)
        self.assertIn(f'init={first}/init', contents)
        self.assertIn(f'initrd /EFI/GLF/generations/{identifier}/initrd', contents)
        self.assertEqual((self.esp / f'EFI/GLF/generations/{identifier}/initrd').read_bytes(), (first / 'initrd').read_bytes())
        self.assertEqual((self.esp / 'EFI/BOOT/BOOTX64.EFI').read_bytes(), (self.bundle / 'shimx64.efi').read_bytes())
        self.assertEqual((self.esp / 'EFI/GLF/grubx64.efi').read_bytes(), (self.bundle / 'systemd-bootx64.efi').read_bytes())

    def test_invalid_signature_preserves_esp(self):
        target = self.target('bad-signature')
        (self.esp / 'loader').mkdir(parents=True)
        (self.esp / 'loader/loader.conf').write_text('old default')
        data = bytearray((self.bundle / 'kernel.efi').read_bytes())
        data[0x20] ^= 1
        (self.bundle / 'kernel.efi').write_bytes(data)
        with self.assertRaises(subprocess.CalledProcessError):
            install(self.config, target, allow_unmounted=True)
        self.assertEqual((self.esp / 'loader/loader.conf').read_text(), 'old default')
        self.assertFalse((self.esp / 'EFI').exists())

    def test_signed_wrong_kernel_rejected(self):
        target = self.target('wrong-kernel')
        shutil.copyfile(self.bundle / 'systemd-bootx64.efi', self.bundle / 'kernel.efi')
        with self.assertRaisesRegex(ValueError, 'ne correspond pas'):
            install(self.config, target, allow_unmounted=True)
        self.assertFalse(self.esp.exists())

    def test_parameter_injection_rejected(self):
        target = self.target('bad-params')
        meta = json.loads((target / 'glf-secureboot.json').read_text())
        for param in ('root=x\nlinux /other.efi', 'module.sig_enforce=0', 'init=/other/init'):
            altered = {**meta, 'kernelParams': meta['kernelParams'] + [param]}
            (target / 'glf-secureboot.json').write_text(json.dumps(altered))
            with self.assertRaises(ValueError):
                install(self.config, target, allow_unmounted=True)
            self.assertFalse(self.esp.exists())


class MultibootTests(BootTests):
    def setUp(self):
        super().setUp()
        self.config['multiboot'] = {'enable': True, 'configurationLimit': 2}
        shutil.copyfile(self.bundle / 'systemd-bootx64.efi', self.bundle / 'refind_x64.efi')
        assets = self.root / 'assets'
        (assets / 'themes/glfos').mkdir(parents=True)
        for file in ('glfos.png', 'glf-bootloader.png'):
            (assets / 'themes/glfos' / file).write_bytes(b'fixture')
        self.addCleanup(patch.stopall)
        patch.dict(os.environ, {'GLF_MULTIBOOT_ASSETS': str(assets)}).start()

    def test_generations_disable_and_unrelated_files(self):
        first, second, third = [self.target(n) for n in ('first', 'second', 'third')]
        for target in (first, second, third, first):
            install(self.config, target, allow_unmounted=True)
        menu = (self.esp / 'EFI/refind/refind.conf').read_text()
        self.assertEqual(menu.count('menuentry "GLF-OS"'), 1)
        self.assertEqual(menu.count('submenuentry '), 2)
        self.assertIn('submenu_on_select true', menu)
        self.assertIn(f'init={first}/init', menu)
        self.assertEqual((self.esp / 'EFI/BOOT/refind.conf').read_text(), menu)
        unrelated = self.esp / 'EFI/ubuntu/shimx64.efi'
        unrelated.parent.mkdir()
        unrelated.write_bytes(b'other OS')
        config = {**self.config, 'multiboot': {'enable': False}}
        install(config, first, allow_unmounted=True)
        self.assertFalse((self.esp / 'EFI/refind').exists())
        self.assertEqual(unrelated.read_bytes(), b'other OS')
        self.assertEqual((self.esp / 'EFI/BOOT/grubx64.efi').read_bytes(),
                         (self.bundle / 'systemd-bootx64.efi').read_bytes())
        self.assertEqual(len(list((self.esp / 'EFI/GLF/generations').iterdir())), 3)

    def test_unmanaged_refind_preserved(self):
        (self.esp / 'EFI/refind').mkdir(parents=True)
        (self.esp / 'EFI/refind/refind.conf').write_text('foreign')
        with self.assertRaisesRegex(ValueError, 'non geree'):
            install(self.config, self.target('first'), allow_unmounted=True)
        self.assertEqual((self.esp / 'EFI/refind/refind.conf').read_text(), 'foreign')
        self.assertFalse((self.esp / 'EFI/GLF').exists())

    def test_unmanaged_fallback_preserved(self):
        (self.esp / 'EFI/BOOT').mkdir(parents=True)
        (self.esp / 'EFI/BOOT/BOOTX64.EFI').write_bytes(b'foreign')
        with self.assertRaisesRegex(ValueError, 'non geree'):
            install(self.config, self.target('first'), allow_unmounted=True)
        self.assertEqual((self.esp / 'EFI/BOOT/BOOTX64.EFI').read_bytes(), b'foreign')

    def test_invalid_refind_signature_preserves_esp(self):
        data = bytearray((self.bundle / 'refind_x64.efi').read_bytes())
        data[0x20] ^= 1
        (self.bundle / 'refind_x64.efi').write_bytes(data)
        with self.assertRaises(subprocess.CalledProcessError):
            install(self.config, self.target('first'), allow_unmounted=True)
        self.assertFalse(self.esp.exists())

    def test_no_nvram_calls_in_simulation(self):
        with patch('multiboot.firmware_state') as state, patch('multiboot.configure_firmware') as configure:
            install(self.config, self.target('first'), allow_unmounted=True)
        state.assert_not_called()
        configure.assert_not_called()


if __name__ == '__main__':
    unittest.main()
