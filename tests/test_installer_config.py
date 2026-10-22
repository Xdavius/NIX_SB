"""Le parcours de signature par poste ne doit plus etre accepte."""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'pkgs/boot-tools/src'))
from install_boot import install, run


class InstallerConfigTests(unittest.TestCase):
    def test_arguments_are_not_shell_code(self):
        command = ['/opt/tool', '--project', 'a b; $(false)']
        with patch('install_boot.subprocess.run') as execute:
            run(*command)
        execute.assert_called_once_with(command, check=True)

    def test_old_signer_rejected_before_filesystem_access(self):
        with patch('install_boot.Path') as path:
            with self.assertRaisesRegex(ValueError, 'signerCommand retire'):
                install({'signerCommand': ['/old/signer']}, '/does-not-exist')
            path.assert_not_called()
