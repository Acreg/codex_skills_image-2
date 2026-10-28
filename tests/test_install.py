"""Portable installer tests; all writes are confined to temporary directories."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

PACKAGE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("portable_installer", PACKAGE / "install.py")
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


class InstallerTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="onemini-installer-test-")
        self.addCleanup(tmp.cleanup)
        self.base = Path(tmp.name)
        self.home = self.base / "another computer user"
        self.codex_home = self.home / "custom Codex folder"
        self.bundle = self.base / "skill package"
        self.bundle.mkdir()
        self.addCleanup(patch.stopall)
        patch.object(Path, "home", return_value=self.home).start()
        patch.dict(os.environ, {"CODEX_HOME": str(self.codex_home)}).start()
        files = {
            "install.py": (PACKAGE / "install.py").read_bytes(),
            "image-image-generation/SKILL.md": b"---\nname: aa-onemini-image-generation\n---\n",
            "image-image-generation/VERSION": b"4.0.1\n",
            "image-image-generation/scripts/run.py": b"print('ready')\n",
        }
        for name, contents in files.items():
            file = self.bundle / name
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_bytes(contents)
        self.make_manifest()

    def make_manifest(self):
        files = {
            file.relative_to(self.bundle).as_posix(): hashlib.sha256(file.read_bytes()).hexdigest()
            for file in self.bundle.rglob("*") if file.is_file() and file.name != "manifest.json"
        }
        (self.bundle / "manifest.json").write_text(
            json.dumps({"schema": 1, "skill": installer.NAME, "files": files}), encoding="utf-8"
        )

    def test_target_uses_current_codex_home(self):
        self.assertEqual(installer.default_skills_dir(), self.codex_home / "skills")
        installed = installer.install(self.bundle, installer.default_skills_dir())
        self.assertEqual(installed["status"], "installed")
        self.assertEqual(Path(installed["target"]), self.codex_home / "skills" / installer.NAME)
        self.assertTrue((Path(installed["target"]) / "scripts/run.py").exists())

    def test_default_without_codex_home(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(installer.default_skills_dir(), self.home / ".codex" / "skills")

    def test_check_has_no_user_side_effects(self):
        installer.verify_bundle(self.bundle)
        self.assertFalse(self.home.exists())

    def test_install_again_is_idempotent(self):
        first = installer.install(self.bundle, installer.default_skills_dir())
        second = installer.install(self.bundle, installer.default_skills_dir())
        self.assertEqual(first["target"], second["target"])
        self.assertEqual(second["status"], "already_installed")

    def test_existing_skill_updated_and_backed_up(self):
        target = self.codex_home / "skills" / installer.NAME
        target.mkdir(parents=True)
        (target / "SKILL.md").write_text("old version", encoding="utf-8")
        (target / "user-settings.txt").write_text("retain", encoding="utf-8")
        (target / "fallback-config.local.json").write_text("local-only-test", encoding="utf-8")
        updated = installer.install(self.bundle, installer.default_skills_dir())
        self.assertEqual(updated["status"], "updated")
        self.assertEqual((Path(updated["backup"]) / "user-settings.txt").read_text(), "retain")
        self.assertEqual((target / "fallback-config.local.json").read_text(), "local-only-test")
        self.assertEqual((target / "SKILL.md").read_bytes(), (self.bundle / installer.NAME / "SKILL.md").read_bytes())

    def test_legacy_location_updated_in_place(self):
        legacy = self.home / ".agents" / "skills" / installer.NAME
        legacy.mkdir(parents=True)
        (legacy / "SKILL.md").write_text("old version", encoding="utf-8")
        with patch.dict(os.environ, {}, clear=True):
            result = installer.install(self.bundle, installer.default_skills_dir())
        self.assertEqual(Path(result["target"]), legacy)
        self.assertFalse((self.codex_home / "skills" / installer.NAME).exists())

    def test_tampering_rejected(self):
        (self.bundle / installer.NAME / "SKILL.md").write_text("tampered")
        with self.assertRaises(ValueError):
            installer.install(self.bundle, installer.default_skills_dir())
        self.assertFalse(self.home.exists())

    def test_cli_check_works_from_other_directory(self):
        checked = subprocess.run(
            [sys.executable, "-B", str(self.bundle / "install.py"), "--check"],
            cwd=self.base, capture_output=True, text=True
        )
        self.assertEqual(checked.returncode, 0, checked.stderr)
        self.assertEqual(json.loads(checked.stdout)["status"], "verified")


if __name__ == "__main__":
    unittest.main()


