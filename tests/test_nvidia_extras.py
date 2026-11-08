"""Exercise missing, partial and complete upstream installs without a GPU/build."""
import json
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


HOOK = Path(__file__).resolve().parents[1] / 'pkgs/drivers/nvidia/install-extras.sh'


@unittest.skipUnless(shutil.which('jq'), 'jq is required')
class NvidiaExtrasTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='nvidia extras ')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'source'
        self.source.mkdir()
        self.out = self.root / 'out'
        self.bin = self.root / 'bin'
        tools = self.root / 'tools'
        tools.mkdir()
        patcher = tools / 'patchelf'
        patcher.write_text('#!/bin/sh\nprintf "%s\\n" "$*" >> "$PATCH_LOG"\n')
        patcher.chmod(0o755)
        cc = self.root / 'cc/nix-support'
        cc.mkdir(parents=True)
        (cc / 'dynamic-linker').write_text('/test/ld.so\n')
        self.env = dict(os.environ, out=str(self.out), bin=str(self.bin),
                        version='620.70.06', libPath='/test/lib', NIX_CC=str(cc.parent),
                        PATCH_LOG=str(self.root / 'patch.log'),
                        PATH=str(tools) + os.pathsep + os.environ['PATH'])
        for name in ['nvidia-pcc', 'nvidia-ngx-updater', 'nvngx_update.exe']:
            (self.source / name).write_bytes(b'upstream source ' + name.encode())
        (self.source / 'sandboxutils-filelist.json').write_text('[{"name":"libcuda.so","type":"LIB"}]')
        (self.source / 'nvidia_icd_vksc.json').write_text(
            '{"ICD":{"library_path":"libnvidia-vksc-core.so.1"}}')
        self.paths = {
            'bin/nvidia-pcc': self.bin / 'bin/nvidia-pcc',
            'origBin/nvidia-pcc': self.bin / 'origBin/nvidia-pcc',
            'bin/nvidia-ngx-updater': self.bin / 'bin/nvidia-ngx-updater',
            'origBin/nvidia-ngx-updater': self.bin / 'origBin/nvidia-ngx-updater',
            'vulkansc/icd': self.out / 'share/vulkansc/icd.d/nvidia_icd.json',
            'sandboxutils/inventory': self.bin / 'share/nvidia/files.d/sandboxutils-filelist.json',
            'wine/ngx-updater': self.out / 'lib/nvidia/wine/nvngx_update.exe',
        }

    def run_hook(self, check=True):
        return subprocess.run(['bash', '-euo', 'pipefail', str(HOOK)],
                              cwd=self.source, env=self.env, check=check,
                              text=True, capture_output=True)

    def report(self):
        return json.loads((self.out / 'nix-support/nvidia-extras.json').read_text())

    def seed(self, names):
        for name in names:
            path = self.paths[name]
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b'existing upstream file ' + name.encode())

    def snapshot(self):
        return {name: (path.read_bytes(), path.stat().st_mtime_ns)
                for name, path in self.paths.items()}

    def test_missing_files_are_added_and_second_run_is_a_noop(self):
        self.run_hook()
        report, files = self.report(), self.snapshot()
        patches = (self.root / 'patch.log').read_bytes()
        self.assertEqual(set(report['addedByNixSb']), set(self.paths))
        self.assertFalse(report['upstreamComplete'])
        self.run_hook()
        self.assertEqual(self.snapshot(), files)
        self.assertEqual(self.report(), report)
        self.assertEqual((self.root / 'patch.log').read_bytes(), patches)

    def test_complete_upstream_is_preserved_and_reported_for_retirement(self):
        self.seed(self.paths)
        files = self.snapshot()
        # When upstream supplies everything, source layout changes must not
        # cause a redundant local installation to access removed source files.
        for path in self.source.iterdir():
            path.unlink()
        result = self.run_hook()
        self.assertEqual(files, self.snapshot())
        self.assertTrue(self.report()['upstreamComplete'])
        self.assertEqual(set(self.report()['providedByNixpkgs']), set(self.paths))
        self.assertIn('can be retired', result.stdout)
        self.assertFalse((self.root / 'patch.log').exists())
        report = self.report()
        self.run_hook()
        self.assertEqual(self.report(), report)
        self.assertEqual(self.snapshot(), files)

    def test_partial_upstream_only_fills_gaps(self):
        native = {'bin/nvidia-pcc', 'vulkansc/icd', 'sandboxutils/inventory'}
        self.seed(native)
        before = {name: self.paths[name].read_bytes() for name in native}
        self.run_hook()
        report = self.report()
        self.assertEqual(set(report['providedByNixpkgs']), native)
        self.assertEqual(set(report['addedByNixSb']), set(self.paths) - native)
        self.assertFalse(report['upstreamComplete'])
        self.assertEqual(before, {name: self.paths[name].read_bytes() for name in native})
        self.run_hook()
        self.assertEqual(self.report(), report)

    def test_upstream_symlink_is_not_overwritten(self):
        self.seed(self.paths)
        link = self.paths['bin/nvidia-pcc']
        link.unlink()
        target = self.root / 'native-pcc'
        target.write_bytes(b'upstream target')
        link.symlink_to(target)
        self.run_hook()
        self.assertTrue(link.is_symlink())
        self.assertEqual(target.read_bytes(), b'upstream target')

    def test_broken_upstream_symlink_is_preserved_for_install_check(self):
        self.seed(self.paths)
        link = self.paths['bin/nvidia-pcc']
        link.unlink()
        link.symlink_to(self.root / 'absent')
        self.run_hook()
        self.assertTrue(link.is_symlink())
        self.assertFalse(link.exists())
        # This is not a successful installation: check-install.py must reject it.
        self.assertIn('bin/nvidia-pcc', self.report()['providedByNixpkgs'])
        spec = importlib.util.spec_from_file_location('nvidia_install_check', HOOK.with_name('check-install.py'))
        checker = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(checker)
        with self.assertRaisesRegex(AssertionError, 'Missing installed file'):
            checker.check_executable(link)

    def test_missing_required_source_fails(self):
        (self.source / 'sandboxutils-filelist.json').unlink()
        self.assertNotEqual(self.run_hook(check=False).returncode, 0)
        self.assertFalse((self.out / 'nix-support/nvidia-extras.json').exists())


@unittest.skipUnless(shutil.which('nix-instantiate'), 'Nix is required')
class NvidiaHookCompositionTests(unittest.TestCase):
    def test_upstream_hooks_checks_and_inputs_are_preserved(self):
        for upstream_hook in ['"upstream-install\\n"', 'null']:
            with self.subTest(upstream_hook=upstream_hook):
                expr = '''let
                  upstream = rec {
                    postInstall = UPSTREAM_HOOK;
                    installCheckPhase = "upstream-phase";
                    postInstallCheck = "upstream-check\\n";
                    nativeInstallCheckInputs = [ "upstream-input" ];
                    overrideAttrs = f: upstream // f upstream;
                  };
                  result = import PACKAGE {
                    nvidiaPackages.mkDriver = _: upstream;
                    lib.optionalString = condition: value: if condition then value else "";
                    stdenv.hostPlatform.isx86_64 = true;
                    python3 = "test-python";
                    patchelf = "test-patchelf";
                  };
                in { inherit (result) postInstall postInstallCheck installCheckPhase nativeInstallCheckInputs; }
                '''.replace('PACKAGE', str(HOOK.with_name('package.nix'))).replace('UPSTREAM_HOOK', upstream_hook)
                result = subprocess.run(['nix-instantiate', '--eval', '--strict', '--json',
                                         '--expr', expr], text=True, capture_output=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                values = json.loads(result.stdout)
                if upstream_hook != 'null':
                    self.assertTrue(values['postInstall'].startswith('upstream-install\n'))
                self.assertIn('extras_missing', values['postInstall'])
                self.assertEqual(values['installCheckPhase'], 'upstream-phase')
                self.assertTrue(values['postInstallCheck'].startswith('upstream-check\n'))
                self.assertIn('check-install.py', values['postInstallCheck'])
                self.assertEqual(values['nativeInstallCheckInputs'],
                                 ['upstream-input', 'test-python', 'test-patchelf'])


if __name__ == '__main__':
    unittest.main()
