"""Affichage local des generations, sans build ni acces EFI."""
import datetime
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pkgs/boot-tools/src"))
from boot_menu import menu_header


class MenuTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.profiles = self.root / "profiles"
        self.profiles.mkdir()

    def target(self, name, label):
        target = self.root / name
        target.mkdir()
        (target / "boot.json").write_text(json.dumps({"org.nixos.bootspec.v1": {"label": label}}))
        return target

    def generation(self, number, target, date):
        link = self.profiles / f"system-{number}-link"
        link.symlink_to(target)
        timestamp = datetime.datetime.fromisoformat(date).timestamp()
        os.utime(link, (timestamp, timestamp), follow_symlinks=False)

    def test_generation_details_and_rollback(self):
        first = self.target("old", "GLF-OS Rising (Linux 6.18.56)")
        second = self.target("new", "GLF-OS Rising (Linux 6.18.57)")
        self.generation(9, first, "2026-10-21")
        self.generation(10, second, "2026-10-23")
        (self.profiles / "system").symlink_to(second)
        for target, number, date in [(second, 10, "2026-10-23"), (first, 9, "2026-10-21")]:
            header = menu_header(target, self.profiles)
            self.assertTrue(header.startswith("title GLF-OS\nversion Generation " + str(number)))
            self.assertIn("built on " + date, header)
        self.assertIn("Linux 6.18.56", menu_header(first, self.profiles))

    def test_same_target_uses_latest_generation_number(self):
        target = self.target("same", "GLF-OS Rising")
        self.generation(9, target, "2026-10-21")
        self.generation(10, target, "2026-10-23")
        (self.profiles / "system-11-link").symlink_to(self.root / "missing")
        self.assertIn("Generation 10", menu_header(target, self.profiles))

    def test_initial_install_without_profile(self):
        target = self.target("initial", "GLF-OS Rising (Linux 6.18.57)")
        header = menu_header(target, self.root / "absent")
        self.assertIn("version GLF-OS Rising (Linux 6.18.57)\n", header)
        self.assertNotIn("Generation", header)
        self.assertNotIn("1970", header)

    def test_old_generation_without_bootspec(self):
        target = self.root / "legacy-system"
        target.mkdir()
        self.assertIn("version legacy-system\n", menu_header(target, self.profiles))
        for content in ("invalid json", "[]", '{"org.nixos.bootspec.v1": null}'):
            (target / "boot.json").write_text(content)
            self.assertIn("version legacy-system\n", menu_header(target, self.profiles))

    def test_label_cannot_inject_boot_directives(self):
        target = self.target("injection", "GLF-OS\nlinux /other.efi\r\noptions init=/bad")
        header = menu_header(target, self.profiles)
        self.assertEqual([line.split()[0] for line in header.splitlines()],
                         ["title", "version", "sort-key"])

    def test_glf_release_omits_any_nixos_codename(self):
        for index, nixos_name in enumerate(("Zokor", "Another NixOS Name")):
            target = self.target(f"release-{index}", f"GLF-OS {nixos_name} Rising (Linux 6.18.57)")
            (target / "etc").mkdir()
            (target / "etc/os-release").write_text('ID=glfos\nVERSION_CODENAME="Rising"\n')
            header = menu_header(target, self.profiles)
            self.assertIn("version GLF-OS Rising (Linux 6.18.57)\n", header)
            self.assertNotIn(nixos_name, header)

    def test_rollback_uses_target_release(self):
        target = self.target("older-release", "GLF-OS OldNixOS OldGLF (Linux 6.12.1)")
        (target / "etc").mkdir()
        (target / "etc/os-release").write_text('ID=glfos\nVERSION_CODENAME="OldGLF"\n')
        self.generation(4, target, "2026-09-01")
        self.assertIn("Generation 4 GLF-OS OldGLF (Linux 6.12.1)", menu_header(target, self.profiles))
