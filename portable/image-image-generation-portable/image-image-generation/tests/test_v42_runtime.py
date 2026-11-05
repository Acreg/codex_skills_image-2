"""Offline v4.2.0 regression tests using synthetic credentials and media."""
import base64
import contextlib
import io
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import threading
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import generate_image as g


class V42RuntimeTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="image-v42-")
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.home = self.root / "codex"
        self.home.mkdir()
        self.env = self.root / ".env"
        self.addCleanup(patch.stopall)
        patch.object(g, "SKILL_ENV_PATH", self.env).start()
        patch.object(g, "GEMINI_CONFIG_PATH", self.root / "no-gemini.json").start()
        patch.object(g, "FALLBACK_PATH", self.root / "fallback.json").start()
        patch.dict(os.environ, {}, clear=True).start()
        self.env.write_text('OPENAI_API_KEY="ENV_TEST"\nOPENAI_BASE_URL="https://env.example/v1"\n', encoding="utf-8")
        self.out = self.root / "result.gif"

    def codex(self, url="https://api.onemini.top/v1", token="CONFIG_TEST"):
        os.environ["CODEX_THREAD_ID"] = "synthetic-thread"
        text = 'model_provider="main"\n[model_providers.main]\nbase_url=' + json.dumps(url) + '\nexperimental_bearer_token=' + json.dumps(token) + '\n'
        (self.home / "config.toml").write_text(text, encoding="utf-8")

    def cli(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with patch.object(sys, "argv", ["generate_image.py", *args]), contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                code = g.main()
            except SystemExit as exc:
                code = exc.code
        return code, out.getvalue(), err.getvalue()

    def gif_bytes(self):
        frames = [Image.new("RGB", (8, 8), color) for color in ("red", "blue", "green", "yellow")]
        raw = io.BytesIO()
        frames[0].save(raw, "GIF", save_all=True, append_images=frames[1:], duration=250, loop=0)
        return raw.getvalue()

    def test_codex_uses_provider_pair_and_ignores_skill_env(self):
        self.codex()
        config = g.discover_api_config(self.home)
        self.assertEqual((config.base_url, config.api_key, config.credential_source),
                         ("https://api.onemini.top/v1", "CONFIG_TEST", "config.toml"))
        self.assertNotIn("CONFIG_TEST", repr(config))

    def test_codex_auth_json_and_active_profile(self):
        os.environ["CODEX_THREAD_ID"] = "synthetic"
        (self.home / "config.toml").write_text('profile="active"\nmodel_provider="wrong"\n[profiles.active]\nmodel_provider="right"\n[model_providers.right]\nbase_url="https://beta.onemini.top/v1"\n', encoding="utf-8")
        (self.home / "auth.json").write_text(json.dumps({"auth_mode": "apikey", "OPENAI_API_KEY": "AUTH_TEST"}), encoding="utf-8")
        config = g.discover_api_config(self.home)
        self.assertEqual((config.base_url, config.api_key), ("https://beta.onemini.top/v1", "AUTH_TEST"))

    def test_codex_provider_env_key(self):
        os.environ.update({"CODEX_THREAD_ID":"synthetic", "PROVIDER_KEY":"ENV_PROVIDER_TEST"})
        (self.home / "config.toml").write_text('model_provider="main"\n[model_providers.main]\nbase_url="https://api.onemini.top"\nenv_key="PROVIDER_KEY"\n', encoding="utf-8")
        self.assertEqual(g.discover_api_config(self.home).api_key, "ENV_PROVIDER_TEST")

    def test_codex_domain_check_cannot_be_bypassed_by_env_or_fallback(self):
        for url in ("https://other.example/v1", "https://api.onemini.top.evil.example/v1", "https://onemini.top/v1"):
            with self.subTest(url=url):
                self.codex(url)
                with self.assertRaises(g.ConfigError) as caught:
                    g.discover_api_config(self.home)
                self.assertIn("仅限连接 Onemini API", str(caught.exception))
        self.codex("https://other.example/v1")
        (self.root / "fallback.json").write_text(json.dumps({"version":1,"base_url":"https://api.onemini.top","api_key":"FALLBACK_TEST"}),encoding="utf-8")
        with patch.object(g, "api_request") as call:
            code, _, err = self.cli("run", "--config-home", str(self.home), "--config-source", "fallback", "--prompt", "test")
        self.assertEqual(code, 2)
        self.assertIn("仅限连接 Onemini API", err)
        call.assert_not_called()

    def test_codex_chatgpt_routes_native_without_network_or_pillow(self):
        os.environ["CODEX_THREAD_ID"] = "synthetic"
        (self.home / "auth.json").write_text(json.dumps({"auth_mode":"chatgpt", "tokens":{"access_token":"SYNTHETIC"}}), encoding="utf-8")
        with patch.object(g, "api_request") as call, patch.object(g, "image_runtime", side_effect=AssertionError("native needs no Pillow")):
            code, out, err = self.cli("run", "--config-home", str(self.home), "--prompt", "test")
        self.assertEqual((code, err), (0, ""))
        self.assertEqual(json.loads(out)["status"], "native_required")
        self.assertNotIn("SYNTHETIC", out)
        call.assert_not_called()

    def test_codex_ambiguous_and_unreadable_api_are_not_native(self):
        os.environ["CODEX_THREAD_ID"] = "synthetic"
        with patch.object(g, "codex_login_status", return_value=None), self.assertRaises(g.ConfigError):
            g.discover_api_config(self.home)
        (self.home / "config.toml").write_text('model_provider="x"\n[model_providers.x]\nbase_url="https://api.onemini.top"\n', encoding="utf-8")
        with patch.object(g, "codex_login_status", return_value="api"), self.assertRaises(g.ConfigError):
            g.discover_api_config(self.home)

    def test_non_codex_uses_skill_env_without_reading_codex(self):
        with patch.object(g, "codex_provider", side_effect=AssertionError("must not read Codex")):
            config = g.discover_api_config(self.home)
        self.assertEqual((config.base_url, config.api_key), ("https://env.example/v1", "ENV_TEST"))

    def test_gemini_missing_key_has_separate_setup_instruction(self):
        with self.assertRaises(g.ConfigError) as caught:
            g.discover_gemini_config(self.home)
        self.assertIn("gemini-cli", str(caught.exception))
        self.assertIn("api.onemini.top", str(caught.exception))

    def test_default_gif_omits_size_and_optional_frame_parameters(self):
        payload = json.loads(g.json_body("test", "auto", "medium", output_format="gif"))
        self.assertEqual(payload["model"], "gpt-image-2.6")
        self.assertEqual(payload["output_format"], "gif")
        self.assertNotIn("size", payload)
        self.assertNotIn("frame_count", payload)
        self.assertNotIn("frame_duration_ms", payload)

    def test_gif_one_post_keeps_original_and_reports_mismatch(self):
        data = self.gif_bytes()
        response = {"data": [{"b64_json":base64.b64encode(data).decode()}]}
        config = g.ApiConfig("https://api.onemini.top/v1", "SYNTHETIC", "test", "test")
        with patch.object(g, "discover_api_config", return_value=config), patch.object(g, "api_request", return_value=response) as request:
            code, out, err = self.cli("run", "--config-home", str(self.home), "--prompt", "fox", "--output-format", "gif", "--frame-count", "15", "--frame-duration-ms", "200", "--out", str(self.out))
        self.assertEqual((code, err), (0, ""))
        self.assertEqual(request.call_count, 1)
        payload = json.loads(request.call_args.args[2])
        self.assertNotIn("size", payload)
        self.assertEqual((payload["frame_count"], payload["frame_duration_ms"]), (15, 200))
        result = json.loads(out)
        self.assertEqual(result["status"], "partial")
        self.assertEqual((result["frame_count"], result["duration_ms"]), (4, 1000))
        self.assertTrue(result["warnings"])
        self.assertEqual(self.out.read_bytes(), data)
        self.assertIn(str(self.out).replace("\\", "/"), result["markdown"])

    def test_gif_end_to_end_sends_one_post_without_size(self):
        received = []
        data = self.gif_bytes()
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                body = self.rfile.read(int(self.headers["Content-Length"]))
                received.append((self.path, json.loads(body), self.headers.get("Authorization")))
                response = json.dumps({"data":[{"b64_json":base64.b64encode(data).decode()}]}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(response)))
                self.end_headers()
                self.wfile.write(response)
            def log_message(self, *args):
                pass
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        config = g.ApiConfig(f"http://127.0.0.1:{server.server_port}/v1", "SYNTHETIC_KEY", "test", "test")
        with patch.object(g, "discover_api_config", return_value=config):
            code, raw, err = self.cli("run", "--config-home", str(self.home), "--prompt", "fox", "--output-format", "gif", "--out", str(self.out))
        self.assertEqual((code, err), (0, ""))
        self.assertEqual(len(received), 1)
        self.assertEqual(received[0][0], "/v1/images/generations")
        self.assertEqual(received[0][2], "Bearer SYNTHETIC_KEY")
        self.assertEqual(received[0][1]["model"], "gpt-image-2.6")
        self.assertNotIn("size", received[0][1])
        self.assertEqual(json.loads(raw)["status"], "ok")
        self.assertEqual(self.out.read_bytes(), data)

    def test_gif_static_response_is_preserved_and_reported_partial(self):
        raw = io.BytesIO()
        Image.new("RGB", (8, 8), "red").save(raw, "PNG")
        response = {"data":[{"b64_json":base64.b64encode(raw.getvalue()).decode()}]}
        config = g.ApiConfig("https://api.onemini.top/v1", "SYNTHETIC", "test", "test")
        with patch.object(g, "discover_api_config", return_value=config), patch.object(g, "api_request", return_value=response):
            code, out, err = self.cli("run", "--config-home", str(self.home), "--prompt", "fox", "--output-format", "gif", "--out", str(self.out))
        self.assertEqual((code, err), (0, ""))
        result = json.loads(out)
        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["image_format"], "PNG")
        self.assertTrue(Path(result["output"]).suffix == ".png")
        self.assertEqual(Path(result["output"]).read_bytes(), raw.getvalue())
        self.assertFalse(self.out.exists())

    def test_gif_size_is_rejected_before_request(self):
        with patch.object(g, "api_request") as call:
            code, _, err = self.cli("run", "--prompt", "fox", "--output-format", "gif", "--size", "1024x1024")
        self.assertEqual(code, 2)
        self.assertIn("GIF 不支持 --size", err)
        call.assert_not_called()

    def test_static_size_4k_passed_unchanged(self):
        payload = json.loads(g.json_body("test", "3840x2160", "medium"))
        self.assertEqual((payload["model"], payload["size"]), ("gpt-image-2.6", "3840x2160"))

    def test_missing_dependency_instructs_user_consent(self):
        with patch.dict(sys.modules, {"PIL": None}), self.assertRaises(g.ConfigError) as caught:
            g.image_runtime()
        self.assertIn("询问用户", str(caught.exception))

if __name__ == "__main__":
    unittest.main()
