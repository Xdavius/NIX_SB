"""Le choix du noyau conserve le defaut et refuse les variantes inconnues."""
import json
from pathlib import Path
import subprocess
import unittest

SELECT = Path(__file__).resolve().parents[1] / 'pkgs/kernel/select.nix'


class KernelVariantTests(unittest.TestCase):
    def evaluate(self, variant):
        expression = '''let
          selected = import SELECT {
            kernelVariant = VARIANT;
            pkgs = {
              linuxPackages_6_18 = { kernel = "stable"; rebuildImage = true; };
              linuxPackages_7_2 = { kernel = "7.2"; rebuildImage = true; };
              linuxPackages_latest = { kernel = "upstream"; rebuildImage = true; };
            };
          };
        in selected.kernel'''.replace('SELECT', str(SELECT)).replace('VARIANT', json.dumps(variant))
        return subprocess.run(['nix-instantiate', '--eval', '--strict', '--json',
                               '--expr', expression], capture_output=True, text=True)

    def test_selection(self):
        for variant, expected in [('default', 'stable'), ('latest', '7.2'), ('upstream-latest', 'upstream')]:
            result = self.evaluate(variant)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout), expected)

    def test_unknown_variant_rejected(self):
        result = self.evaluate('typo')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('kernelVariant', result.stderr)
