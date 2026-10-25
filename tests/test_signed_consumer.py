"""Evaluate the real consumer package without building kernels or downloading releases."""
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class SignedConsumer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='signed-consumer-')
        cls.addClassCleanup(cls.temp.cleanup)
        cls.work = Path(cls.temp.name)
        release = cls.work / 'release.json'
        release.write_text(json.dumps(dict(version=2, commit='a' * 40, branch='Rising',
                                          profile='testing', url='https://invalid/archive',
                                          archiveHash='sha256-' + 'A' * 43 + '=')))
        # Real Nix derivation contexts with a deliberately unbuildable catalogue.
        expr = '''let
          runCommand = name: attrs: script:
            (builtins.derivation ({ inherit name; system = "x86_64-linux";
              builder = "/not-a-builder"; builderScript = script;
            } // attrs)) // { inherit script; };
          driver = runCommand "unselected-nvidia" {} "exit 99";
          kernel = (runCommand "catalogue-kernel" {} "${driver}") // { version = "test"; };
          tool = runCommand "consumer-tools" {} "";
          signed = import MODULE {
            inherit runCommand kernel;
            lib.escapeShellArg = value: "'" + value + "'";
            fetchurl = args: runCommand "published-archive" {} args.url;
            python3 = tool; openssl = tool; sbsigntool = tool; jq = tool;
            systemd = tool; refind = tool; rockyShim = tool;
            releaseFile = RELEASE;
          };
        in {
          kernelPath = toString kernel;
          kernelDrv = kernel.drvPath;
          driverDrv = driver.drvPath;
          kernelContext = builtins.getContext kernel.script;
          bundleContext = builtins.getContext signed.bundle.script;
          consumerContext = builtins.getContext signed.kernel.script;
          auditContext = builtins.getContext signed.verifiedBuild.script;
          bundleDrv = signed.bundle.drvPath;
          script = signed.bundle.script;
        }'''.replace('MODULE', str(ROOT / 'pkgs/signed/default.nix')).replace('RELEASE', str(release))
        cls.result = json.loads(subprocess.check_output(
            ['nix-instantiate', '--eval', '--strict', '--json', '--expr', expr], text=True))

    def test_consumer_does_not_require_catalogue_build(self):
        r = self.result
        self.assertIn(r['driverDrv'], r['kernelContext'])
        for context in ('bundleContext', 'consumerContext'):
            self.assertNotIn(r['kernelDrv'], r[context])
            self.assertNotIn(r['driverDrv'], r[context])
        self.assertIn(r['bundleDrv'], r['consumerContext'])

    def test_explicit_audit_still_requires_rebuilt_kernel(self):
        self.assertIn(self.result['kernelDrv'], self.result['auditContext'])
        self.assertIn(self.result['bundleDrv'], self.result['auditContext'])

    def verify_provenance(self, content):
        with tempfile.TemporaryDirectory(prefix='signed-provenance-') as directory:
            root = Path(directory)
            # Exercise the actual Python verification emitted by the Nix package.
            # PE equality is independent of the provenance cases under test here.
            (root / 'signing_protocol.py').write_text('def pe_content(path): return b"same PE"\n')
            if content is not None:
                (root / 'store-paths.txt').write_text(content)
            code = self.result['script'].split("python3 - <<'PY'\n", 1)[1].split('\nPY\n', 1)[0]
            return subprocess.run(['python3', '-c', code], cwd=root, capture_output=True, text=True)

    def test_matching_published_kernel_accepted(self):
        result = self.verify_provenance(self.result['kernelPath'] + '\n/another/output\n')
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_wrong_published_kernel_rejected(self):
        result = self.verify_provenance('/nix/store/other-kernel\n')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Noyau incompatible', result.stderr)

    def test_missing_or_empty_provenance_rejected(self):
        for content in (None, ''):
            with self.subTest(content=content):
                self.assertNotEqual(self.verify_provenance(content).returncode, 0)


if __name__ == '__main__':
    unittest.main()
