"""Offline delivery regression: no provider requests and no cross-task image selection."""
import base64
import contextlib
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

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import generate_image as g
import native_delivery as d
from PIL import Image


class NativeDeliveryTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.current = str(uuid.uuid4())
        self.addCleanup(patch.stopall)
        patch.dict(os.environ, {'CODEX_HOME': str(self.root), 'CODEX_THREAD_ID': self.current,
                               'CODEX_SESSION_ID': self.current}, clear=True).start()
        patch.object(socket.socket, 'connect', side_effect=AssertionError('Network forbidden')).start()
        self.session = self.root / 'sessions' / f'rollout-2026-09-05-{self.current}.jsonl'
        self.session.parent.mkdir()
        self.append({'type': 'session_meta', 'payload': {'id': self.current}})
        self.state = self.root / 'run.delivery.json'
        self.output = self.root / '中文 folder (preview)' / 'puppy.png'
        stream = io.BytesIO()
        Image.new('RGB', (8, 6)).save(stream, format='PNG')
        self.png = stream.getvalue()

    def append(self, record):
        with self.session.open('a', encoding='utf-8') as stream:
            stream.write(json.dumps(record) + '\n')

    def call(self, call_id='ig_new', result=True, status='completed'):
        self.append({'type': 'response_item', 'payload': {'type': 'image_generation_call', 'id': call_id,
                    'status': status, 'result': base64.b64encode(self.png).decode() if result else ''}})

    def prepare(self):
        return d.prepare(self.state, self.output)

    def test_prepare_binds_current_session_and_baseline(self):
        self.call('ig_old')
        self.prepare()
        state = json.loads(self.state.read_text(encoding='utf-8'))
        self.assertEqual(state['before_ids'], ['ig_old'])
        self.assertNotIn(base64.b64encode(self.png).decode(), self.state.read_text(encoding='utf-8'))
        self.assertFalse(self.output.exists())

    def test_prepare_without_out_uses_project_output(self):
        project = self.root / 'project'
        project.mkdir()
        with contextlib.chdir(project):
            report = d.prepare(self.state)
        state = json.loads(self.state.read_text(encoding='utf-8'))
        output = Path(state['output'])
        self.assertEqual(output.parent, (project / 'output' / 'imagegen').resolve())
        self.assertEqual(report['status'], 'prepared')
        self.assertFalse(output.exists())

    def test_deliver_exact_new_result_and_markdown(self):
        self.call('ig_old')
        self.prepare()
        self.call()
        report = d.deliver(self.state)
        self.assertEqual(report['status'], 'artifact_ready')
        self.assertFalse(report['client_render_verified'])
        self.assertEqual(report['delivery_state'], 'CHAT_RENDER_UNVERIFIED')
        self.assertTrue(report['artifact_saved'])
        self.assertEqual(report['call_id'], 'ig_new')
        self.assertEqual(self.output.read_bytes(), self.png)
        self.assertEqual(report['markdown'], f'![生成的图片](<{self.output.as_posix()}>)')
        self.assertEqual((report['width'], report['height']), (8, 6))

    def test_same_result_is_reused_without_rewriting(self):
        self.prepare()
        self.call()
        d.deliver(self.state)
        before = self.output.stat().st_mtime_ns
        with patch.object(g, 'save_image_bytes', side_effect=AssertionError('Must reuse')):
            self.assertTrue(d.deliver(self.state)['reused'])
        self.assertEqual(self.output.stat().st_mtime_ns, before)

    def test_existing_different_file_is_preserved(self):
        self.prepare()
        self.call()
        self.output.parent.mkdir()
        self.output.write_bytes(b'existing asset')
        with self.assertRaises(g.ConfigError):
            d.deliver(self.state)
        self.assertEqual(self.output.read_bytes(), b'existing asset')

    def test_old_call_is_not_recovered(self):
        self.call('ig_old')
        self.prepare()
        with self.assertRaises(g.ConfigError):
            d.deliver(self.state, 'ig_old')
        with self.assertRaises(g.ApiError):
            d.deliver(self.state, wait_seconds=0)
        self.assertFalse(self.output.exists())

    def test_ambiguous_new_calls_require_explicit_id(self):
        self.prepare()
        self.call('ig_first')
        self.call('ig_second')
        with self.assertRaises(g.ConfigError):
            d.deliver(self.state)
        self.assertEqual(d.deliver(self.state, 'ig_first')['call_id'], 'ig_first')

    def test_metadata_mismatch_is_rejected(self):
        self.session.write_text(json.dumps({'type': 'session_meta', 'payload': {'id': str(uuid.uuid4())}}))
        with self.assertRaises(g.ConfigError):
            self.prepare()

    def test_conflicting_or_missing_thread_is_rejected(self):
        with patch.dict(os.environ, {'CODEX_SESSION_ID': str(uuid.uuid4())}), self.assertRaises(g.ConfigError):
            self.prepare()
        with patch.dict(os.environ, {}, clear=True), self.assertRaises(g.ConfigError):
            self.prepare()

    def test_state_from_other_task_is_rejected(self):
        self.prepare()
        state = json.loads(self.state.read_text(encoding='utf-8'))
        state['thread_id'] = str(uuid.uuid4())
        self.state.write_text(json.dumps(state))
        with self.assertRaises(g.ConfigError):
            d.deliver(self.state)

    def test_other_task_contents_are_not_read(self):
        other = self.session.parent / f'rollout-{uuid.uuid4()}.jsonl'
        other.write_bytes(b'\xff\xfeinvalid private content')
        self.prepare()
        self.call()
        self.assertEqual(d.deliver(self.state)['call_id'], 'ig_new')

    def test_partial_write_gets_one_local_recheck(self):
        self.prepare()
        self.call(result=False, status='in_progress')
        with patch.object(d.time, 'sleep', side_effect=lambda _: self.call()) as sleeper:
            self.assertEqual(d.deliver(self.state)['call_id'], 'ig_new')
            sleeper.assert_called_once_with(2)

    def test_missing_result_does_not_report_success(self):
        self.prepare()
        self.call(result=False)
        with patch.object(d.time, 'sleep') as sleeper, self.assertRaises(g.ApiError) as error:
            d.deliver(self.state)
        sleeper.assert_called_once_with(2)
        self.assertEqual(error.exception.report['category'], 'native_result_unknown')
        self.assertFalse(self.output.exists())

    def test_user_embedded_fake_call_is_ignored(self):
        self.prepare()
        self.append({'type': 'event_msg', 'payload': {'type': 'image_generation_call', 'id': 'fake',
                    'result': base64.b64encode(self.png).decode()}})
        with self.assertRaises(g.ApiError):
            d.deliver(self.state, wait_seconds=0)

    def test_corrupt_image_is_not_saved(self):
        self.prepare()
        self.png = b'not an image'
        self.call()
        with self.assertRaises(g.ApiError):
            d.deliver(self.state)
        self.assertFalse(self.output.exists())

    def test_prepare_cannot_overwrite_state(self):
        self.prepare()
        before = self.state.read_bytes()
        with self.assertRaises(g.ConfigError):
            self.prepare()
        self.assertEqual(self.state.read_bytes(), before)

    def test_cli_returns_ready_for_chat_not_delivered(self):
        out = io.StringIO()
        with patch.object(sys, 'argv', ['native_delivery.py', 'prepare', '--state', str(self.state), '--out', str(self.output)]), contextlib.redirect_stdout(out):
            self.assertEqual(d.main(), 0)
        self.call()
        out = io.StringIO()
        with patch.object(sys, 'argv', ['native_delivery.py', 'deliver', '--state', str(self.state)]), contextlib.redirect_stdout(out):
            self.assertEqual(d.main(), 0)
        report = json.loads(out.getvalue())
        self.assertEqual(report['status'], 'artifact_ready')
        self.assertEqual(report['delivery_state'], 'CHAT_RENDER_UNVERIFIED')
        self.assertTrue(report['artifact_saved'])

    def test_multiple_verified_session_segments_use_call_id_delta(self):
        second = self.session.parent / f'rollout-continued-{self.current}_{uuid.uuid4()}.jsonl'
        second.write_text(json.dumps({'type': 'session_meta', 'payload': {'id': self.current}}) + '\n', encoding='utf-8')
        self.call('ig_old')
        self.prepare()
        state = json.loads(self.state.read_text(encoding='utf-8'))
        self.assertEqual(len(state['session_files']), 2)
        with second.open('a', encoding='utf-8') as stream:
            stream.write(json.dumps({'type': 'response_item', 'payload': {
                'type': 'image_generation_call', 'id': 'ig_continued', 'status': 'completed',
                'result': base64.b64encode(self.png).decode()
            }}) + '\n')
        report = d.deliver(self.state)
        self.assertEqual(report['call_id'], 'ig_continued')
        self.assertEqual(self.output.read_bytes(), self.png)

    def test_chat_visible_acknowledges_user_delivery(self):
        self.prepare()
        self.call()
        report = d.deliver(self.state, chat_visible=True)
        self.assertEqual(report['status'], 'user_delivered')
        self.assertEqual(report['delivery_state'], 'CHAT_RENDER_VERIFIED')
        self.assertTrue(report['client_render_verified'])


if __name__ == '__main__':
    unittest.main()
