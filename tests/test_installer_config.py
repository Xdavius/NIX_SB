"""Contrat du signataire externe, sans assemblage UKI ni acces firmware."""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'pkgs/boot-tools/src'))
from install_boot import install, run, signer_command


class SignerTests(unittest.TestCase):
    def test_arguments_are_not_shell_code(self):
        command = ['/opt/signer', '--project', 'a b; $(false)']
        self.assertEqual(signer_command({'signerCommand': command}), command)
        with patch('install_boot.subprocess.run') as execute:
            run(*command)
        execute.assert_called_once_with(command, check=True)

    def test_invalid_signer_rejected_before_filesystem_access(self):
        for value in (None, '', 'sh -c signer', [], [42], ['']):
            with self.subTest(value=value), patch('install_boot.Path') as path:
                with self.assertRaisesRegex(ValueError, 'signerCommand'):
                    install({'signerCommand': value}, '/does-not-exist')
                path.assert_not_called()
