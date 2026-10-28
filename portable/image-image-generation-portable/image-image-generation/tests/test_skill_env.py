import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import generate_image as g

class SkillEnvTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.home = Path(tmp.name) / "codex"
        self.home.mkdir()
        self.env = Path(tmp.name) / ".env"
        self.legacy = Path(tmp.name) / "gemini.json"
        self.addCleanup(patch.stopall)
        patch.object(g, "SKILL_ENV_PATH", self.env).start()
        patch.object(g, "GEMINI_CONFIG_PATH", self.legacy).start()
        patch.dict(os.environ, {}, clear=True).start()

    def test_codex_auth_and_provider_default(self):
        self.env.write_text('OPENAI_API_KEY = ""\nOPENAI_BASE_URL = ""\nGEMINI_API_KEY = ""\n')
        (self.home / "auth.json").write_text(json.dumps({"OPENAI_API_KEY": "GPT_TEST"}))
        (self.home / "config.toml").write_text('model_provider="user"\n[model_providers.user]\nbase_url="https://codex.example/v1"\n')
        config = g.discover_api_config(self.home)
        self.assertEqual(config.api_key, "GPT_TEST")
        self.assertEqual(config.base_url, "https://codex.example/v1")
        self.assertEqual(config.credential_source, "auth.json")
        self.assertEqual(config.endpoint_source, "config.toml")

    def test_gpt_explicit_file_override(self):
        (self.home / "auth.json").write_text(json.dumps({"OPENAI_API_KEY": "CODEX_TEST"}))
        self.env.write_text('OPENAI_API_KEY = "FILE_TEST"\nOPENAI_BASE_URL = "https://file.example/v1"\n')
        config = g.discover_api_config(self.home)
        self.assertEqual(config.api_key, "FILE_TEST")
        self.assertEqual(config.base_url, "https://file.example/v1")

    def test_gemini_isolated_and_env_not_exported(self):
        (self.home / "auth.json").write_text(json.dumps({"OPENAI_API_KEY": "GPT_TEST"}))
        self.env.write_text('GEMINI_API_KEY = "GEMINI_TEST"\nGEMINI_BASE_URL = "https://gemini.example/v1beta"\n')
        config = g.discover_gemini_config(self.home)
        self.assertEqual(config.api_key, "GEMINI_TEST")
        self.assertEqual(config.base_url, "https://gemini.example/v1beta")
        self.assertNotIn("GEMINI_API_KEY", os.environ)
        self.assertNotIn("GEMINI_TEST", json.dumps(g.gemini_config_report()))

    def test_missing_gemini_never_borrows_gpt(self):
        self.env.write_text('GEMINI_API_KEY = ""\n')
        (self.home / "auth.json").write_text(json.dumps({"OPENAI_API_KEY": "GPT_TEST"}))
        with self.assertRaises(g.ConfigError):
            g.discover_gemini_config(self.home)

    def test_legacy_gemini_config_kept(self):
        self.env.write_text('GEMINI_API_KEY = ""\nGEMINI_BASE_URL = "https://api.onemini.top/v1beta"\n')
        self.legacy.write_text(json.dumps({"version": 1, "api_key": "LEGACY_TEST", "base_url": "https://old.example/v1beta"}))
        config = g.discover_gemini_config(self.home)
        self.assertEqual(config.api_key, "LEGACY_TEST")
        self.assertEqual(config.base_url, "https://old.example/v1beta")

    def test_native_delivery_contract_remains(self):
        root = Path(__file__).resolve().parents[1]
        skill = (root / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("native_delivery.py prepare", skill)
        self.assertIn("native_delivery.py deliver", skill)
        self.assertIn("output/imagegen/", skill)
        self.assertIn("markdown", skill)
        self.assertTrue((root / "scripts" / "native_delivery.py").is_file())
