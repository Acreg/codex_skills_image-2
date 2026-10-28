"""Offline project-output and concurrent delivery tests; no image API calls."""
import base64
from concurrent.futures import ThreadPoolExecutor
import io
import json
import os
from pathlib import Path
import socket
import sys
import tempfile
import unittest
from unittest.mock import patch
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import generate_image as g
import native_delivery as d
from PIL import Image


class OutputParallelTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.addCleanup(patch.stopall)
        patch.object(socket.socket, "connect", side_effect=AssertionError("Network forbidden")).start()

    def test_default_output_stays_project_relative(self):
        with patch.object(Path, "cwd", return_value=self.root):
            output = g.default_output()
        self.assertEqual(output.parent, Path("output/imagegen"))
        self.assertFalse(output.is_absolute())
        self.assertTrue(str((self.root / output).resolve()).startswith(str(self.root)))

    def test_skill_cwd_refuses_default_output(self):
        for cwd in (g.SKILL_ROOT, g.SKILL_ROOT / "scripts"):
            with self.subTest(cwd=cwd), patch.object(Path, "cwd", return_value=cwd):
                with self.assertRaises(g.ConfigError):
                    g.default_output()

    def test_same_timestamp_concurrent_names_are_unique(self):
        with patch.object(Path, "cwd", return_value=self.root), patch.object(g, "datetime") as clock:
            clock.now.return_value.strftime.return_value = "same-timestamp"
            # Worker count is a test setting, not an installed skill concurrency limit.
            with ThreadPoolExecutor(max_workers=8) as executor:
                names = list(executor.map(lambda _: g.default_output(), range(128)))
        self.assertEqual(len(set(names)), 128)

    def png(self, color):
        stream = io.BytesIO()
        Image.new("RGB", (8, 6), color).save(stream, format="PNG")
        return stream.getvalue()

    def test_concurrent_outputs_keep_correct_bytes(self):
        images = [self.png((n * 20, 0, 0)) for n in range(8)]
        outputs = [self.root / "project output" / f"image-{n}.png" for n in range(8)]
        with ThreadPoolExecutor(max_workers=8) as executor:
            reports = list(executor.map(lambda pair: g.save_image_bytes(*pair), zip(images, outputs)))
        for image, output, report in zip(images, outputs, reports):
            self.assertEqual(output.read_bytes(), image)
            self.assertIn(output.name, report["markdown"])

    def prepare_two_calls(self):
        current = str(uuid.uuid4())
        patch.dict(os.environ, {"CODEX_HOME": str(self.root), "CODEX_THREAD_ID": current,
                               "CODEX_SESSION_ID": current}, clear=True).start()
        session = self.root / "sessions" / f"rollout-{current}.jsonl"
        session.parent.mkdir()
        session.write_text(json.dumps({"type": "session_meta", "payload": {"id": current}}) + "\n", encoding="utf-8")
        states = [self.root / f"state-{n}.delivery.json" for n in range(2)]
        outputs = [self.root / "output" / f"picture-{n}.png" for n in range(2)]
        for state, output in zip(states, outputs):
            d.prepare(state, output)
        images = [self.png("red"), self.png("blue")]
        # Reverse completion order to prove recovery binds by ID, never by newest result.
        with session.open("a", encoding="utf-8") as stream:
            for n in (1, 0):
                stream.write(json.dumps({"type": "response_item", "payload": {
                    "type": "image_generation_call", "id": f"ig_{n}", "status": "completed",
                    "result": base64.b64encode(images[n]).decode("ascii")}}) + "\n")
        return states, outputs, images

    def test_parallel_recovery_is_bound_to_explicit_call_ids(self):
        states, outputs, images = self.prepare_two_calls()
        with ThreadPoolExecutor(max_workers=2) as executor:
            reports = list(executor.map(lambda n: d.deliver(states[n], f"ig_{n}"), range(2)))
        for n in range(2):
            self.assertEqual(outputs[n].read_bytes(), images[n])
            self.assertEqual(reports[n]["call_id"], f"ig_{n}")

    def test_parallel_recovery_without_id_refuses_to_guess(self):
        states, outputs, _ = self.prepare_two_calls()
        with self.assertRaises(g.ConfigError):
            d.deliver(states[0])
        self.assertFalse(any(output.exists() for output in outputs))


if __name__ == "__main__":
    unittest.main()
