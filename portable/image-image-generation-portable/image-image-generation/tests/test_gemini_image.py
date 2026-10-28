"""Gemini v1beta native image forwarding: local HTTP server, synthetic images and key."""
import base64
import contextlib
import io
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import generate_image as g
REAL_DISCOVER_GEMINI = g.discover_gemini_config
from PIL import Image


class GeminiTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        image_bytes = io.BytesIO()
        Image.new("RGB", (8, 6), (30, 50, 70)).save(image_bytes, format="PNG")
        self.png = image_bytes.getvalue()
        self.received = []
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                outer.received.append((self.command, self.path, dict(self.headers), None))
                data = {"models": [{"name": "models/gemini-nano-banana-2.1",
                                    "supportedGenerationMethods": ["generateContent"]}]}
                self.respond(data)

            def do_POST(self):
                length = int(self.headers["Content-Length"])
                request = json.loads(self.rfile.read(length))
                outer.received.append((self.command, self.path, dict(self.headers), request))
                data = getattr(outer, "result", {
                    "candidates": [{"content": {"parts": [
                        {"text": "completed"},
                        {"inlineData": {"mimeType": "image/png",
                                        "data": base64.b64encode(outer.png).decode()}}
                    ]}}]
                })
                self.respond(data)

            def respond(self, payload):
                data = json.dumps(payload).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, *args):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        thread.start()
        config = g.ApiConfig(base_url=f"http://127.0.0.1:{self.server.server_port}/v1beta",
                             api_key="SYNTHETIC_TEST_KEY", endpoint_source="test",
                             credential_source="test")
        self.discover = patch.object(g, "discover_gemini_config", return_value=config)
        self.discover.start()
        self.addCleanup(self.discover.stop)

    def cli(self, args):
        output, errors = io.StringIO(), io.StringIO()
        with patch.object(sys, "argv", ["generate_image.py", *args]), \
                contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            result = g.main()
        return result, output.getvalue(), errors.getvalue()

    def test_independent_keys_and_urls(self):
        home = self.root / "codex-home"
        home.mkdir()
        local = self.root / "gemini-config.local.json"
        with patch.object(g, "GEMINI_CONFIG_PATH", local):
            g.configure_gemini({"api_key": "LOCAL_GEMINI_KEY", "base_url": "https://gemini.example/v1beta"})
            with patch.dict(g.os.environ, {
                "OPENAI_API_KEY": "GPT_ONLY_KEY", "OPENAI_BASE_URL": "https://gpt.example/v1",
                "GEMINI_API_KEY": "ENV_GEMINI_KEY", "GEMINI_BASE_URL": "https://gemini.example/v1beta"
            }, clear=True):
                config = REAL_DISCOVER_GEMINI(home)
                self.assertEqual(config.api_key, "LOCAL_GEMINI_KEY")
                self.assertEqual(config.base_url, "https://gemini.example/v1beta")
                self.assertNotEqual(config.api_key, "GPT_ONLY_KEY")
            with patch.dict(g.os.environ, {"OPENAI_API_KEY": "GPT_ONLY_KEY"}, clear=True):
                config = REAL_DISCOVER_GEMINI(home)
                self.assertEqual(config.api_key, "LOCAL_GEMINI_KEY")
                self.assertEqual(config.base_url, "https://gemini.example/v1beta")

    def test_gemini_missing_key_does_not_reuse_gpt_key(self):
        with patch.object(g, "GEMINI_CONFIG_PATH", self.root / "missing-gemini.json"), patch.dict(
            g.os.environ, {"OPENAI_API_KEY": "GPT_ONLY_KEY", "OPENAI_BASE_URL": "https://gpt.example/v1"}, clear=True
        ):
            with self.assertRaises(g.ConfigError) as error:
                REAL_DISCOVER_GEMINI(self.root)
            self.assertIn("不会复用 GPT", str(error.exception))

    def test_gpt_model_uses_gpt_key(self):
        gpt = g.ApiConfig("http://127.0.0.1:1234/v1", "GPT_ONLY_KEY", "test", "test")
        with patch.object(g, "discover_api_config", return_value=gpt), patch.object(
            g, "api_request", return_value={"data": [{"b64_json": base64.b64encode(self.png).decode()}]}
        ) as request:
            code, raw, error = self.cli(["run", "--model", "gpt-image-2.5-flare",
                                         "--prompt", "gpt test", "--out", str(self.root / "gpt.png")])
        self.assertEqual(code, 0, error)
        self.assertEqual(request.call_args.args[0], "http://127.0.0.1:1234/v1/images/generations")
        self.assertEqual(request.call_args.args[1], "GPT_ONLY_KEY")

    def test_configure_gemini_cli_uses_stdin(self):
        local = self.root / "gemini-only.json"
        data = json.dumps({"api_key": "GEMINI_ONLY_SECRET", "base_url": "https://api.onemini.top/v1beta"})
        with patch.object(g, "GEMINI_CONFIG_PATH", local), patch.object(sys, "stdin", io.StringIO(data)):
            code, raw, error = self.cli(["configure-gemini"])
        self.assertEqual(code, 0, error)
        self.assertEqual(json.loads(raw)["status"], "saved")
        self.assertTrue(local.is_file())
        self.assertNotIn("GEMINI_ONLY_SECRET", raw + error)

    def test_native_generate_and_parameters(self):
        path = self.root / "result.png"
        code, raw, error = self.cli([
            "run", "--model", "gemini-nano-banana-2.1", "--prompt", "a test image",
            "--aspect-ratio", "16:9", "--image-size", "2K", "--thinking-level", "minimal",
            "--google-search", "--image-only", "--out", str(path)
        ])
        self.assertEqual(code, 0, error)
        self.assertEqual(len(self.received), 1)
        method, route, headers, body = self.received[0]
        self.assertEqual(method, "POST")
        self.assertEqual(route, "/v1beta/models/gemini-nano-banana-2.1:generateContent")
        self.assertEqual(headers["Authorization"], "Bearer SYNTHETIC_TEST_KEY")
        self.assertEqual(body["generationConfig"], {
            "responseModalities": ["IMAGE"], "imageConfig": {"aspectRatio": "16:9", "imageSize": "2K"},
            "thinkingConfig": {"thinkingLevel": "minimal"}
        })
        self.assertEqual(body["tools"], [{"googleSearch": {}}])
        self.assertEqual(body["contents"][0]["parts"][0]["text"], "a test image")
        self.assertEqual(json.loads(raw)["api_protocol"], "gemini-v1beta")
        self.assertTrue(path.exists())
        with Image.open(path) as image:
            self.assertEqual(image.size, (8, 6))

    def test_edit_reference_image_and_webp_output(self):
        source = self.root / "reference.jpg"
        Image.new("RGB", (8, 6), (10, 20, 30)).save(source)
        dest = self.root / "edited.webp"
        code, raw, error = self.cli(["edit", "--model", "gemini-nano-banana-2.1",
                                      "--prompt", "edit this", "--image", str(source),
                                      "--output-format", "webp", "--out", str(dest)])
        self.assertEqual(code, 0, error)
        parts = self.received[0][3]["contents"][0]["parts"]
        self.assertEqual(parts[1]["inlineData"]["mimeType"], "image/jpeg")
        self.assertTrue(base64.b64decode(parts[1]["inlineData"]["data"]).startswith(b"\xff\xd8"))
        with Image.open(dest) as image:
            self.assertEqual(image.format, "WEBP")
        self.assertEqual(json.loads(raw)["operation"], "edit")

    def test_real_model_listing_get_without_image_generation(self):
        code, raw, error = self.cli(["list-models"])
        self.assertEqual(code, 0, error)
        self.assertEqual(self.received[0][:2], ("GET", "/v1beta/models"))
        self.assertEqual(len(self.received), 1)
        self.assertEqual(json.loads(raw)["models"][0]["name"], "models/gemini-nano-banana-2.1")
        self.assertEqual(self.received[0][2]["Authorization"], "Bearer SYNTHETIC_TEST_KEY")

    def test_two_images_saved(self):
        encoded = base64.b64encode(self.png).decode()
        self.result = {"candidates": [{"content": {"parts": [
            {"inlineData": {"mimeType": "image/png", "data": encoded}},
            {"inlineData": {"mimeType": "image/png", "data": encoded}}
        ]}}]}
        destination = self.root / "multi.png"
        code, raw, error = self.cli(["run", "--model", g.GEMINI_MODEL, "--prompt", "two images",
                                     "--out", str(destination)])
        self.assertEqual(code, 0, error)
        data = json.loads(raw)
        self.assertEqual(data["image_count"], 2)
        self.assertTrue((self.root / "multi-2.png").is_file())
        self.assertEqual(len(data["outputs"]), 2)

    def test_text_only_response_fails(self):
        self.result = {"candidates": [{"content": {"parts": [{"text": "no image"}]}}]}
        code, raw, error = self.cli(["run", "--model", g.GEMINI_MODEL,
                                     "--prompt", "test", "--out", str(self.root / "fail.png")])
        self.assertEqual(code, 1)
        self.assertIn("empty_image_result", error)
        self.assertFalse((self.root / "fail.png").exists())

    def test_gemini_rejects_openai_only_parameter_without_post(self):
        code, _, error = self.cli(["run", "--model", g.GEMINI_MODEL, "--prompt", "a",
                                   "--background", "transparent", "--out", str(self.root / "bad.png")])
        self.assertEqual(code, 2)
        self.assertEqual(len(self.received), 0)

    def test_gpt_does_not_send_gemini_parameters(self):
        code, _, error = self.cli(["run", "--prompt", "a", "--aspect-ratio", "16:9",
                                   "--out", str(self.root / "bad.png")])
        self.assertEqual(code, 2)
        self.assertEqual(len(self.received), 0)


if __name__ == "__main__":
    unittest.main()
