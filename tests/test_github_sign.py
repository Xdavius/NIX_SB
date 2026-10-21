"""Exercise GitHub request orchestration without credentials or network."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import github_sign
from signing_protocol import IMAGES


class ClientTests(unittest.TestCase):
    def exercise(self, visibility='PRIVATE', conclusion='success', mismatch=False):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            unsigned, signed = root / 'unsigned', root / 'signed'
            unsigned.mkdir()
            for name in IMAGES:
                (unsigned / name).write_bytes(b'fixture')
            calls = []
            tag = None

            def gh(*args):
                nonlocal tag
                calls.append(args)
                if args[:2] == ('repo', 'view'):
                    return json.dumps({'visibility': visibility})
                if args[:2] == ('release', 'create'):
                    tag = args[2]
                if args[:2] == ('run', 'list'):
                    return json.dumps([{'databaseId': 42, 'displayTitle': tag}])
                if args[:2] == ('run', 'view'):
                    return json.dumps({'status': 'completed', 'conclusion': conclusion})
                if args[:2] == ('run', 'download'):
                    (signed / 'request.json').write_bytes(b'wrong' if mismatch else (unsigned / 'request.json').read_bytes())
                return ''

            argv = ['glf-github-sign', '--repo', 'GLF/test', '--certificate', 'public.pem',
                    '--system', '/nix/store/test-system', str(unsigned), str(signed)]
            with patch.object(sys, 'argv', argv), patch.object(github_sign, 'gh', gh), \
                 patch.object(github_sign, 'verify_response') as verify:
                if visibility == 'PUBLIC':
                    with self.assertRaises(SystemExit):
                        github_sign.main()
                    self.assertEqual(len(calls), 1)
                elif conclusion != 'success':
                    with self.assertRaises(RuntimeError):
                        github_sign.main()
                    self.assertFalse(signed.exists())
                elif mismatch:
                    with self.assertRaises(ValueError):
                        github_sign.main()
                    verify.assert_not_called()
                else:
                    github_sign.main()
                    verify.assert_called_once_with(unsigned, signed, 'public.pem')
                    upload = next(c for c in calls if c[:2] == ('release', 'upload'))
                    self.assertEqual({Path(p).name for p in upload[5:]}, {*IMAGES, 'request.json'})

    def test_success(self):
        self.exercise()

    def test_public_refused(self):
        self.exercise(visibility='PUBLIC')

    def test_signature_failure(self):
        self.exercise(conclusion='failure')

    def test_wrong_request(self):
        self.exercise(mismatch=True)


if __name__ == '__main__':
    unittest.main()
