import json
import subprocess
import unittest
from unittest.mock import patch

from ci.prune_releases import main, obsolete_releases


def release(number, **overrides):
    return {'id': number, 'tag_name': f'secureboot-testing-{"a" * 12}-{number:040x}',
            'draft': False, 'published_at': f'2026-10-{number:02d}T05:23:00Z', **overrides}


class PruneReleasesTests(unittest.TestCase):
    def test_keep_seven_by_publication_date(self):
        releases = [release(n) for n in range(1, 11)]
        self.assertEqual(obsolete_releases(releases, releases[-1]['tag_name']),
                         [release(n)['tag_name'] for n in (3, 2, 1)])

    def test_small_repository_unchanged(self):
        self.assertEqual(obsolete_releases([release(1)], release(1)['tag_name']), [])

    def test_drafts_and_unrelated_releases_untouched(self):
        releases = [release(n) for n in range(1, 8)]
        releases += [release(8, draft=True), release(9, tag_name='other-product-v1')]
        self.assertEqual(obsolete_releases(releases, release(7)['tag_name']), [])

    def test_global_limit_and_new_tag_format(self):
        releases = [release(n) for n in range(1, 9)]
        releases[-1]['tag_name'] = f'secureboot-current-{"b" * 12}-{"c" * 40}-{"d" * 64}'
        self.assertEqual(obsolete_releases(releases, releases[-1]['tag_name']),
                         [release(1)['tag_name']])

    def test_current_publication_protected(self):
        releases = [release(n) for n in range(1, 10)]
        self.assertEqual(obsolete_releases(releases, release(1)['tag_name']),
                         [release(3)['tag_name'], release(2)['tag_name']])

    def test_missing_publication_fails_closed(self):
        with self.assertRaises(ValueError):
            obsolete_releases([release(1)], release(2)['tag_name'])

    @patch.dict('os.environ', {'GITHUB_REPOSITORY': 'fixture/repo'})
    def test_paginated_api_and_deletion(self):
        releases = [release(n) for n in range(1, 9)]
        response = subprocess.CompletedProcess([], 0, json.dumps([releases[:4], releases[4:]]))
        with patch('sys.argv', ['prune', release(8)['tag_name']]), \
                patch('ci.prune_releases.subprocess.run', return_value=response) as run:
            main()
            self.assertEqual(run.call_count, 2)
            self.assertEqual(run.call_args.args[0], [
                'gh', 'release', 'delete', release(1)['tag_name'],
                '--repo', 'fixture/repo', '--yes', '--cleanup-tag'])

    @patch.dict('os.environ', {'GITHUB_REPOSITORY': 'fixture/repo'})
    def test_api_failure_never_deletes(self):
        with patch('ci.prune_releases.subprocess.run',
                   side_effect=subprocess.CalledProcessError(1, 'gh')) as run:
            with self.assertRaises(subprocess.CalledProcessError):
                main()
            self.assertEqual(run.call_count, 1)
