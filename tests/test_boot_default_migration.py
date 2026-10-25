"""Installer migration from rEFInd with no LoaderInfo; all EFI calls mocked."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'pkgs/boot-tools/src'))
import install_boot as installer


class DefaultMigrationTests(unittest.TestCase):
    def test_migration_without_loader_info(self):
        for can_write, fail_write in [(True, False), (False, False), (True, True)]:
            with self.subTest(can_write=can_write, fail_write=fail_write), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                esp, target, bundle = [root / name for name in ('esp', 'target', 'bundle')]
                for p in (esp / 'EFI/refind', target, bundle):
                    p.mkdir(parents=True)
                (esp / 'EFI/refind/.glf-managed').write_text('managed')
                for name in ('kernel.efi', 'systemd-bootx64.efi', 'shimx64.efi', 'mmx64.efi'):
                    (bundle / name).write_bytes(b'fixture')
                (target / 'init').write_text('fixture')
                (target / 'initrd').write_bytes(b'initrd')
                (root / 'cert.pem').write_text('fixture')
                (root / 'cert.cer').write_bytes(b'fixture')
                (target / 'glf-secureboot.json').write_text(json.dumps({
                    'version': 2, 'signedBundle': str(bundle), 'kernel': str(bundle / 'kernel.efi'),
                    'initrd': str(target / 'initrd'), 'kernelParams': ['quiet']}))
                config = {'esp': str(esp), 'certificate': str(root / 'cert.pem'),
                          'timeout': '5', 'canTouchEfiVariables': can_write,
                          'installFallback': False, 'multiboot': {'enable': False}}
                calls = []
                def execute(*args, **kwargs):
                    calls.append(args)
                    if args[0] == 'bootctl':
                        if '--variables=yes' not in args or fail_write:
                            raise subprocess.CalledProcessError(1, args)
                with patch.object(installer, 'validate_esp', return_value=esp), \
                     patch.object(installer, 'pe_content', return_value=b'fixture'), \
                     patch.object(installer, 'run', side_effect=execute), \
                     patch.object(installer.multiboot, 'firmware_state', return_value={}), \
                     patch.object(installer.multiboot, 'configure_firmware'):
                    if fail_write:
                        with self.assertRaises(subprocess.CalledProcessError):
                            installer.install(config, target)
                        self.assertTrue((esp / 'EFI/refind').exists())
                    else:
                        installer.install(config, target)
                        self.assertFalse((esp / 'EFI/refind').exists())
                        self.assertEqual((esp / 'EFI/GLF/grubx64.efi').read_bytes(), b'fixture')
                bootctl = [call for call in calls if call[0] == 'bootctl']
                self.assertEqual(len(bootctl), int(can_write))
                if can_write:
                    self.assertIn('--variables=yes', bootctl[0])


if __name__ == '__main__':
    unittest.main()
