from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'pkgs/boot-tools/src'))
from multiboot import cleanup, configure_firmware, parse_firmware, quoted, render_menu

TEXT = r'''BootOrder: 0002,0001,0003
Boot0001* GLF-OS Multiboot HD(1,GPT,aaaa,0x800,0x1000)/File(\EFI\refind\shimx64.efi)
Boot0002* Windows Boot Manager HD(1,GPT,bbbb,0x800,0x1000)/File(\EFI\Microsoft\Boot\bootmgfw.efi)
Boot0003* Linux Boot Manager HD(1,GPT,bbbb,0x800,0x1000)/File(\EFI\systemd\systemd-bootx64.efi)
'''


class MultibootTests(unittest.TestCase):
    def state(self):
        entries, order = parse_firmware(TEXT)
        return {'entries': entries, 'order': order, 'partuuid': 'aaaa', 'pkname': 'nvme0n1', 'partn': 1}

    def test_discovery_preserves_other_disks(self):
        item = {'kernel': '/kernel', 'initrd': '/initrd', 'options': 'init=/system/init', 'label': 'Generation 1'}
        menu = render_menu([item], 10, self.state())
        self.assertNotIn('firmware_bootnum 0001', menu)
        self.assertIn('firmware_bootnum 0002', menu)
        self.assertIn('firmware_bootnum 0003', menu)
        self.assertIn(r'icons\os_win.png', menu)
        self.assertIn(r'loader "\kernel"', menu)
        self.assertIn(r'initrd "\initrd"', menu)

    def test_make_default_false_preserves_order(self):
        with patch('multiboot.subprocess.run') as run:
            configure_firmware(self.state(), True, False)
        run.assert_not_called()

    def test_make_default_true_moves_only_glf(self):
        with patch('multiboot.subprocess.run') as run:
            configure_firmware(self.state(), True, True)
        run.assert_called_once_with(['efibootmgr', '--bootorder', '0001,0002,0003'], check=True)

    def test_new_entry_without_stealing_default(self):
        state = self.state()
        state['entries'] = state['entries'][1:]
        state['order'] = ['0002', '0003']
        with patch('multiboot.subprocess.run') as run, patch('multiboot.subprocess.check_output', return_value=TEXT):
            configure_firmware(state, True, False)
        self.assertIn('--create-only', run.call_args_list[0].args[0])
        self.assertEqual(run.call_args_list[1].args[0], ['efibootmgr', '--bootorder', '0002,0003,0001'])

    def test_quote_injection_and_control_characters(self):
        self.assertEqual(quoted('a"b'), '"a""b"')
        with self.assertRaises(ValueError):
            quoted('other\nloader /bad')

    def test_targeted_cleanup(self):
        with tempfile.TemporaryDirectory() as temporary:
            esp = Path(temporary)
            for file in ('EFI/GLF/.glf-managed', 'EFI/Linux/nixos-generation-1.efi',
                         'EFI/Linux/other.efi', 'EFI/nixos/kernel-old.efi',
                         'loader/entries/glf-other-old.conf', 'loader/entries/ubuntu.conf'):
                path = esp / file
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('fixture')
            cleanup(esp, True)
            self.assertFalse((esp / 'EFI/Linux/nixos-generation-1.efi').exists())
            self.assertFalse((esp / 'EFI/nixos/kernel-old.efi').exists())
            self.assertTrue((esp / 'EFI/Linux/other.efi').exists())
            self.assertTrue((esp / 'loader/entries/ubuntu.conf').exists())
