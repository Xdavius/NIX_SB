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


    def test_bare_paths_and_inactive_entry(self):
        text = TEXT.replace('Boot0001*', 'Boot0001 ').replace(
            r'File(\EFI\refind\shimx64.efi)', r'\EFI\refind\shimx64.efi')
        entries, order = parse_firmware(text)
        self.assertEqual(entries[0]['path'], r'\efi\refind\shimx64.efi')
        self.assertFalse(entries[0]['active'])
        state = {**self.state(), 'entries': entries, 'order': order}
        with patch('multiboot.subprocess.run') as run:
            configure_firmware(state, True, False)
        run.assert_called_once_with(['efibootmgr', '--bootnum', '0001', '--active'], check=True)

    def test_bootnext_redirected_only_for_direct_loader_on_same_esp(self):
        for path, partition, redirect in [
            (r'\efi\systemd\systemd-bootx64.efi', 'aaaa', True),
            (r'\efi\systemd\systemd-bootx64.efi', 'bbbb', False),
            (r'\efi\microsoft\boot\bootmgfw.efi', 'aaaa', False),
        ]:
            with self.subTest(path=path, partition=partition):
                state = self.state()
                state['entries'].append({'number': '0004', 'active': True,
                                         'path': path, 'partition': partition})
                state['boot_next'] = '0004'
                with patch('multiboot.subprocess.run') as run:
                    configure_firmware(state, True, False)
                if redirect:
                    run.assert_called_once_with(['efibootmgr', '--bootnext', '0001'], check=True)
                else:
                    run.assert_not_called()

    def test_existing_candidate_in_bootorder_is_preferred(self):
        state = self.state()
        state['entries'].append({**state['entries'][0], 'number': '0004'})
        state['order'] = ['0002', '0004', '0001', '0003']
        with patch('multiboot.subprocess.run') as run:
            configure_firmware(state, True, True)
        run.assert_called_once_with(['efibootmgr', '--bootorder', '0004,0002,0001,0003'], check=True)

    def test_bootnext_updated_before_removing_obsolete_entry(self):
        state = self.state()
        state['entries'].append({'number': '0004', 'active': True,
                                 'path': r'\efi\refind\refind_x64.efi', 'partition': 'aaaa'})
        state['boot_next'] = '0004'
        with patch('multiboot.subprocess.run') as run:
            configure_firmware(state, True, False)
        self.assertEqual([call.args[0] for call in run.call_args_list], [
            ['efibootmgr', '--bootnext', '0001'],
            ['efibootmgr', '--delete-bootnum', '--bootnum', '0004']])

    def test_firmware_state_reads_bootnext(self):
        import json
        from multiboot import firmware_state
        with patch('multiboot.subprocess.check_output', side_effect=[
            '/dev/sda1', json.dumps({'blockdevices': [
                {'pkname': 'sda', 'partn': 1, 'partuuid': 'aaaa'}]}),
            TEXT + 'BootNext: 0003\n',
        ]):
            self.assertEqual(firmware_state('/boot')['boot_next'], '0003')

    def test_creation_failure_and_write_failure_propagate(self):
        state = self.state()
        state['entries'] = []
        with patch('multiboot.subprocess.run'), patch('multiboot.subprocess.check_output', return_value=''):
            with self.assertRaisesRegex(ValueError, 'introuvable'):
                configure_firmware(state, True, False)
        with patch('multiboot.subprocess.run', side_effect=RuntimeError('EFI write failed')):
            with self.assertRaisesRegex(RuntimeError, 'EFI write failed'):
                configure_firmware(self.state(), True, True)

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
