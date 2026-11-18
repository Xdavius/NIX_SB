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
              linuxPackages_7_3 = { kernel = "7.3"; rebuildImage = true; };
              linuxPackages_latest = { kernel = "upstream"; rebuildImage = true; };
            };
          };
        in selected.kernel'''.replace('SELECT', str(SELECT)).replace('VARIANT', json.dumps(variant))
        return subprocess.run(['nix-instantiate', '--eval', '--strict', '--json',
                               '--expr', expression], capture_output=True, text=True)

    def test_selection(self):
        for variant, expected in [('default', 'stable'), ('latest', '7.3'), ('upstream-latest', 'upstream')]:
            result = self.evaluate(variant)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout), expected)

    def test_unknown_variant_rejected(self):
        result = self.evaluate('typo')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('kernelVariant', result.stderr)


class NvidiaVariantTests(unittest.TestCase):
    def evaluate(self, variant):
        driver_dir = SELECT.parents[1] / 'drivers/nvidia'
        expression = '''let
          kernelVariant = VARIANT;
          nvidiaPackages = {
            mkDriver = args: {
              inherit (args) version;
              open = { inherit (args) version; origin = "pin"; };
            };
            latest = {
              version = "999.0";
              open = { version = "999.0"; origin = "channel"; };
            };
          };
          driver = import PACKAGE { inherit nvidiaPackages kernelVariant; };
          modules = import MODULES {
            inherit kernelVariant;
            callPackage = path: args: import path ({ inherit nvidiaPackages; } // args);
          };
        in { inherit (driver) version; inherit modules; }
        '''.replace('VARIANT', json.dumps(variant)).replace(
            'PACKAGE', str(driver_dir / 'package.nix')).replace(
            'MODULES', str(driver_dir / 'default.nix'))
        return subprocess.run(['nix-instantiate', '--eval', '--strict', '--json',
                               '--expr', expression], capture_output=True, text=True)

    def check_pin(self, variant):
        result = self.evaluate(variant)
        self.assertEqual(result.returncode, 0, result.stderr)
        pin = json.loads((SELECT.parents[1] / 'drivers/nvidia/version.json').read_text())[variant]
        self.assertEqual(json.loads(result.stdout), {
            'version': pin['version'],
            'modules': {'version': pin['version'], 'origin': 'pin'},
        })

    def test_published_variants_keep_pin(self):
        for variant in ('default', 'latest'):
            with self.subTest(variant=variant):
                self.check_pin(variant)

    def test_upstream_latest_follows_channel_for_package_and_modules(self):
        result = self.evaluate('upstream-latest')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {
            'version': '999.0',
            'modules': {'version': '999.0', 'origin': 'channel'},
        })

    def test_unknown_variant_rejected(self):
        result = self.evaluate('typo')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('NVIDIA: variante noyau inconnue', result.stderr)
