"""Validation legere du fichier distribue, sans Nix ni compilation."""
import json
from pathlib import Path
import unittest


class CatalogueTests(unittest.TestCase):
    def test_entries(self):
        root = Path(__file__).resolve().parents[1] / "pkgs/drivers"
        catalogue = json.loads((root / "catalogue.json").read_text())
        self.assertIsInstance(catalogue, dict)
        self.assertTrue(catalogue)
        for name, entry in catalogue.items():
            with self.subTest(driver=name):
                self.assertIn(set(entry), ({"package"}, {"path"}))
                value = next(iter(entry.values()))
                self.assertIsInstance(value, str)
                self.assertTrue(value)
                if "path" in entry:
                    self.assertTrue(value.startswith("./"))
                    self.assertNotIn("..", Path(value).parts)
                    self.assertTrue((root / value / "default.nix").is_file())
