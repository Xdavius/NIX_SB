import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'ci'))
from approved_source import approved_source


class SourceTests(unittest.TestCase):
    def test_reviewed_revision_required(self):
        base = 'git+https://framagit.org/xdavius/glf-os.git'
        pinned = base + '?ref=feature/secureboot-uki&rev=' + 'a' * 40 + '&dir=secureboot'
        with patch.object(Path, 'read_text', return_value=json.dumps({'flake': pinned})):
            self.assertEqual(approved_source(), pinned)
        for source in (base + '?ref=feature/secureboot-uki&dir=secureboot', 'path:/tmp/untrusted',
                       pinned.replace('glf-os.git', 'other.git'), pinned.replace('a' * 40, 'HEAD')):
            with self.subTest(source=source), patch.object(Path, 'read_text', return_value=json.dumps({'flake': source})):
                with self.assertRaises(ValueError):
                    approved_source()


if __name__ == '__main__':
    unittest.main()
