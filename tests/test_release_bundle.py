"""Refuser toute publication commune incomplete ou incoherente."""
import base64
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
import unittest

from ci.release_bundle import validate_bundle
from ci.release_tag import release_tag


class ReleaseBundleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.metadata = dict(profile='testing', branch='main', commit='a' * 40,
                             channels={'nixpkgs': {'rev': 'b' * 40}})
        self.tag = release_tag(self.metadata)
        (self.root / 'tag.txt').write_text(self.tag)
        for variant in ('default', 'latest'):
            archive = self.root / f'glf-secureboot-{variant}.tar.gz'
            archive.write_bytes(variant.encode())
            self.write(f'build-{variant}.json', dict(self.metadata, kernelVariant=variant))
            self.write(f'release-{variant}.json', dict(
                {key: self.metadata[key] for key in ('profile', 'branch', 'commit')},
                version=2, kernelVariant=variant,
                archiveHash='sha256-' + base64.b64encode(hashlib.sha256(archive.read_bytes()).digest()).decode(),
                url=f'https://github.com/fixture/repo/releases/download/{self.tag}/{archive.name}',
            ))

    def write(self, name, value):
        (self.root / name).write_text(json.dumps(value))

    def change(self, name, **changes):
        value = json.loads((self.root / name).read_text())
        self.write(name, {**value, **changes})

    def test_complete_bundle(self):
        self.assertEqual(validate_bundle(self.root), self.tag)

    def test_missing_variant(self):
        (self.root / 'glf-secureboot-latest.tar.gz').unlink()
        with self.assertRaises(FileNotFoundError):
            validate_bundle(self.root)

    def test_different_channels_rejected(self):
        self.change('build-latest.json', channels={'nixpkgs': {'rev': 'c' * 40}})
        with self.assertRaises(ValueError):
            validate_bundle(self.root)

    def test_wrong_descriptor_rejected(self):
        self.change('release-latest.json', kernelVariant='default')
        with self.assertRaises(ValueError):
            validate_bundle(self.root)

    def test_corrupt_archive_rejected(self):
        (self.root / 'glf-secureboot-latest.tar.gz').write_bytes(b'corrupt')
        with self.assertRaises(ValueError):
            validate_bundle(self.root)

    def test_wrong_url_rejected(self):
        self.change('release-latest.json', url='https://invalid/other')
        with self.assertRaises(ValueError):
            validate_bundle(self.root)

    def test_wrong_tag_rejected(self):
        (self.root / 'tag.txt').write_text('other')
        with self.assertRaises(ValueError):
            validate_bundle(self.root)

    @unittest.skipUnless(shutil.which('jq'), 'jq requis pour le script de publication')
    def test_publish_uploads_both_before_promotion(self):
        repo = Path(__file__).resolve().parents[1]
        work = self.root / 'work'
        (work / 'dist').mkdir(parents=True)
        (work / 'ci').symlink_to(repo / 'ci', target_is_directory=True)
        (work / 'dist/release').symlink_to(self.root, target_is_directory=True)
        mock = work / 'gh'
        public = dict(tag_name=self.tag, draft=False, id=1,
                      published_at='2026-11-05T10:00:00Z')
        mock.write_text(f"""#!{sys.executable}
import json
import sys
from pathlib import Path
with Path('calls.jsonl').open('a') as stream:
    stream.write(json.dumps(sys.argv[1:]) + '\\n')
if sys.argv[1] == 'api':
    print({json.dumps([[public]])!r})
""")
        mock.chmod(0o755)
        env = dict(os.environ, GITHUB_REPOSITORY='fixture/repo',
                   PATH=str(work) + ':' + os.environ['PATH'])
        result = subprocess.run(['bash', str(repo / 'ci/publish-release.sh')],
                                cwd=work, env=env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        calls = [json.loads(line) for line in (work / 'calls.jsonl').read_text().splitlines()]
        self.assertEqual(calls[0][:2], ['release', 'create'])
        self.assertIn('--draft', calls[0])
        for variant in ('default', 'latest'):
            for name in (f'glf-secureboot-{variant}.tar.gz', f'release-{variant}.json', f'build-{variant}.json'):
                self.assertIn('dist/release/' + name, calls[0])
        self.assertEqual(calls[1][:2], ['release', 'edit'])
        self.assertIn('--draft=false', calls[1])
        self.assertEqual(calls[2][0], 'api')
        # A missing variant must stop before any API mutation.
        (work / 'calls.jsonl').unlink()
        (self.root / 'glf-secureboot-latest.tar.gz').unlink()
        result = subprocess.run(['bash', str(repo / 'ci/publish-release.sh')],
                                cwd=work, env=env, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((work / 'calls.jsonl').exists())
