"""Detection des releases sans appels GitHub reels."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from ci.channels import channel_info
from ci.release_tag import release_tag

ROOT = Path(__file__).resolve().parents[1]


class ReleaseNeededTests(unittest.TestCase):
    def test_release_states_and_api_failure(self):
        with tempfile.TemporaryDirectory() as temp:
            work = Path(temp)
            (work / 'ci').symlink_to(ROOT / 'ci', target_is_directory=True)
            lock = {'root': 'root', 'nodes': {
                'root': {'inputs': {
                    'testing-channels': 'channel',
                    'testing-nixpkgs': ['testing-channels', 'nixpkgs'],
                    'testing-nixpkgs-unstable': ['testing-channels', 'nixpkgs-unstable'],
                }},
                'channel': {
                    'locked': {'url': 'https://example.invalid/channel', 'rev': 'a' * 40, 'narHash': 'fixture'},
                    'inputs': {'nixpkgs': 'pkgs', 'nixpkgs-unstable': 'pkgs'},
                },
                'pkgs': {'locked': {'rev': 'b' * 40, 'narHash': 'fixture'}},
            }}
            (work / 'flake.lock').write_text(json.dumps(lock))
            mock = work / 'gh'
            mock.write_text('#!/bin/sh\ncat releases.json\nexit "${MOCK_EXIT:-0}"\n')
            mock.chmod(0o755)
            output = work / 'output'
            env = {**os.environ, 'PATH': str(work) + ':' + os.environ['PATH'],
                   'GITHUB_REPOSITORY': 'fixture/repo', 'GITHUB_REF_NAME': 'Rising',
                   'GITHUB_SHA': 'c' * 40, 'GLF_CHANNEL': 'testing', 'GITHUB_OUTPUT': str(output)}
            for variant in ('default', 'latest'):
                env['GLF_KERNEL_VARIANT'] = variant
                tag = release_tag({'profile': 'testing', 'branch': 'Rising',
                                   'commit': 'c' * 40, 'kernelVariant': variant,
                                   'channels': channel_info(lock, 'testing')})
                other_tag = release_tag({'profile': 'testing', 'branch': 'Rising',
                                         'commit': 'c' * 40,
                                         'kernelVariant': 'latest' if variant == 'default' else 'default',
                                         'channels': channel_info(lock, 'testing')})
                cases = [([], 'true'), ([{'tag_name': tag, 'draft': False}], 'false'),
                         ([{'tag_name': tag, 'draft': True}], 'true'),
                         ([{'tag_name': tag + '-old', 'draft': False}], 'true'),
                         ([{'tag_name': other_tag, 'draft': False}], 'true')]
                for releases, needed in cases:
                    with self.subTest(variant=variant, releases=releases):
                        output.write_text('')
                        (work / 'releases.json').write_text(json.dumps([releases]))
                        result = subprocess.run(['bash', str(ROOT / 'ci/release-needed.sh')],
                                                cwd=work, env=env, capture_output=True, text=True)
                        self.assertEqual(result.returncode, 0, result.stderr)
                        self.assertEqual(output.read_text(), f'needed={needed}\n')
            output.write_text('')
            result = subprocess.run(['bash', str(ROOT / 'ci/release-needed.sh')],
                                    cwd=work, env={**env, 'MOCK_EXIT': '1'}, capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(output.read_text(), '')
