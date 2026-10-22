"""Refus du bootstrap, sans cle generee ni appel reseau."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class BootstrapTests(unittest.TestCase):
    def test_local_execution_refused(self):
        result = subprocess.run(['bash', str(ROOT / 'ci/bootstrap-key.sh')],
                                env={'PATH': os.environ['PATH']}, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('reserve a la CI', result.stderr)

    def test_existing_secret_never_replaced(self):
        for secret in ('GLF_SIGNING_KEY_PEM', 'GLF_SIGNING_CERT_PEM'):
            with self.subTest(secret=secret), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                gh = root / 'gh'
                gh.write_text('#!/bin/sh\n[ "$1 $2" = "secret list" ] || exit 99\ncase "$*" in *"--env glf-signing-production"*) ;; *) exit 98 ;; esac\nprintf "%s\\n" ' + secret + '\n')
                gh.chmod(0o700)
                openssl = root / 'openssl'
                openssl.write_text('#!/bin/sh\ntouch "' + str(root / 'generated') + '"\nexit 99\n')
                openssl.chmod(0o700)
                env = {'PATH': tmp + ':' + os.environ['PATH'], 'GITHUB_ACTIONS': 'true',
                       'GH_TOKEN': 'fixture', 'GITHUB_REPOSITORY': 'fixture/fixture'}
                result = subprocess.run(['bash', str(ROOT / 'ci/bootstrap-key.sh')],
                                        env=env, capture_output=True, text=True)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('aucune regeneration', result.stderr)
                self.assertFalse((root / 'generated').exists())
