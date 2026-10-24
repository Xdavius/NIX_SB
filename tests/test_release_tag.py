"""Les channels mouvants ne doivent pas reutiliser le tag d'un ancien build."""
import copy
import unittest

from ci.release_tag import release_tag


class ReleaseTagTests(unittest.TestCase):
    def setUp(self):
        self.metadata = {
            'profile': 'testing', 'branch': 'Rising', 'commit': 'a' * 40,
            'channels': {'commit': 'b' * 40, 'nixpkgs': {'rev': 'c' * 40}},
        }

    def test_stable_independent_of_key_order(self):
        other = copy.deepcopy(self.metadata)
        other['channels'] = dict(reversed(list(other['channels'].items())))
        self.assertEqual(release_tag(self.metadata), release_tag(other))

    def test_each_source_change_has_its_own_release(self):
        for field, value in [('commit', 'd' * 40), ('branch', 'Next'), ('profile', 'current')]:
            other = {**self.metadata, field: value}
            self.assertNotEqual(release_tag(self.metadata), release_tag(other))
        other = copy.deepcopy(self.metadata)
        other['channels']['nixpkgs']['rev'] = 'e' * 40
        self.assertNotEqual(release_tag(self.metadata), release_tag(other))

    def test_invalid_metadata_rejected(self):
        with self.assertRaises(ValueError):
            release_tag({**self.metadata, 'commit': 'invalid'})


if __name__ == '__main__':
    unittest.main()
