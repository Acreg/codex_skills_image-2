"""Offline regression tests; all credentials are generated synthetic test values."""
import base64
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import socket
import sys
import tempfile
import unittest
from unittest.mock import patch, MagicMock
import urllib.error
import urllib.request
import uuid
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import generate_image as g
from image_errors import upstream_error, redact, HTTP_GUIDANCE
import package_skill
from PIL import Image


class SkillTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.key = 'test-only-' + uuid.uuid4().hex
        self.config = self.root / 'fallback-config.local.json'
        self.output = self.root / 'image.png'
        self.addCleanup(patch.stopall)
        patch.dict(os.environ, {"CODEX_HOME": str(self.root)}, clear=True).start()
        patch.object(g, 'FALLBACK_PATH', self.config).start()
        patch.object(socket.socket, 'connect', side_effect=AssertionError('Real network is forbidden')).start()
        stream = io.BytesIO()
        Image.new('RGB', (8, 6), (20, 40, 80)).save(stream, format='PNG')
        self.png = stream.getvalue()
        self.result = {'data': [{'b64_json': base64.b64encode(self.png).decode()}]}

    def cli(self, args, stdin=''):
        out, err = io.StringIO(), io.StringIO()
        with patch.object(sys, 'argv', ['generate_image.py', *args]), patch.object(sys, 'stdin', io.StringIO(stdin)), contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                code = g.main()
            except SystemExit as exc:
                code = exc.code
        return code, out.getvalue(), err.getvalue()

    def mock_response(self, payload):
        response = MagicMock()
        response.__enter__.return_value = response
        response.read.return_value = payload
        response.headers = {}
        opener = MagicMock()
        opener.open.return_value = response
        return opener

    def test_url_normalization(self):
        for url in ('https://api.openai.com', 'https://api.openai.com/', 'https://api.openai.com/v1', 'https://api.openai.com/v1/'):
            with self.subTest(url=url):
                self.assertEqual(g.normalize_base_url(url, https_only=True), 'https://api.openai.com/v1')

    def test_reject_unsafe_fallback_addresses(self):
        for url in ('http://example.test', 'ftp://example.test', 'https://user:secret@example.test', 'https://example.test?token=x', 'https://example.test/#x', 'https://example.test:bad', 'https://bad host', 'no-url'):
            with self.subTest(url=url), self.assertRaises(g.ConfigError):
                g.configure_fallback({'base_url': url, 'api_key': self.key})
        self.assertFalse(self.config.exists())

    def test_configure_default_offline_without_echo(self):
        with patch.object(g, 'api_request') as request:
            code, out, err = self.cli(['configure-fallback'], json.dumps({'api_key': self.key}))
        self.assertEqual(code, 0)
        self.assertNotIn(self.key, out + err)
        report = json.loads(out)
        self.assertFalse(report['endpoint_verified'])
        self.assertEqual(report['status'], 'saved')
        config = json.loads(self.config.read_text())
        self.assertEqual(set(config), {'version', 'base_url', 'api_key'})
        self.assertEqual(config['api_key'], self.key)
        self.assertEqual(config['base_url'], 'https://api.openai.com/v1')
        request.assert_not_called()
        self.assertEqual(list(self.root.iterdir()), [self.config])

    def test_replace_requires_separate_confirmation(self):
        g.configure_fallback({'api_key': self.key})
        old = self.config.read_bytes()
        data = {'base_url': 'https://new.example.test', 'api_key': 'test-only-' + uuid.uuid4().hex}
        code, _, _ = self.cli(['configure-fallback', '--force'], json.dumps(data))
        self.assertEqual(code, 2)
        self.assertEqual(self.config.read_bytes(), old)
        code, out, _ = self.cli(['configure-fallback', '--replace-config'], json.dumps(data))
        self.assertEqual(code, 0)
        self.assertNotIn(data['api_key'], out)
        self.assertEqual(g.load_fallback().base_url, 'https://new.example.test/v1')
        self.assertEqual(list(self.root.iterdir()), [self.config])

    def test_atomic_failure_preserves_old_configuration(self):
        g.configure_fallback({'api_key': self.key})
        before = self.config.read_bytes()
        with patch.object(os, 'replace', side_effect=OSError('test failure')), self.assertRaises(g.ConfigError):
            g.configure_fallback({'api_key': 'test-only-other'}, replace=True)
        self.assertEqual(self.config.read_bytes(), before)
        self.assertEqual(list(self.root.iterdir()), [self.config])

    def test_malformed_stdin_and_arguments_do_not_echo(self):
        for args, stdin in [(['configure-fallback'], self.key), (['configure-fallback', '--api-key', self.key], '')]:
            with self.subTest(args=args[0]):
                code, out, err = self.cli(args, stdin)
                self.assertEqual(code, 2)
                self.assertNotIn(self.key, out + err)
                self.assertIn('configuration_error', err)

    def test_missing_invalid_and_valid_config_check(self):
        code, out, _ = self.cli(['config-check', '--config-source', 'fallback'])
        self.assertEqual(code, 0)
        self.assertFalse(json.loads(out)['fallback_mode']['available'])
        self.config.write_text(self.key)
        code, out, err = self.cli(['config-check', '--config-source', 'fallback'])
        self.assertNotIn(self.key, out + err)
        self.assertFalse(json.loads(out)['fallback_mode']['available'])
        g.configure_fallback({'api_key': self.key}, replace=True)
        code, out, err = self.cli(['config-check', '--config-source', 'fallback'])
        self.assertTrue(json.loads(out)['fallback_mode']['available'])
        self.assertNotIn(self.key, out + err)

    def test_unknown_config_version_and_invalid_key(self):
        self.config.write_text(json.dumps({'version': 2, 'api_key': self.key}))
        with self.assertRaises(g.ConfigError):
            g.load_fallback()
        for key in ('', 'a b', 'a\nb', None):
            with self.subTest(key=key), self.assertRaises(g.ConfigError):
                g.validate_fallback({'api_key': key})

    def test_existing_and_fallback_configs_are_isolated(self):
        g.configure_fallback({'api_key': self.key})
        env_key = 'test-env-' + uuid.uuid4().hex
        with patch.dict(os.environ, {'OPENAI_API_KEY': env_key, 'OPENAI_BASE_URL': 'https://existing.example.test'}):
            existing = g.discover_api_config(self.root)
            fallback = g.load_fallback()
        self.assertEqual(existing.api_key, env_key)
        self.assertEqual(existing.base_url, 'https://existing.example.test/v1')
        self.assertEqual(fallback.api_key, self.key)
        self.assertEqual(fallback.base_url, 'https://api.openai.com/v1')
        self.assertNotIn(self.key, repr(fallback))

    def test_existing_auth_and_provider_compatibility(self):
        (self.root / 'auth.json').write_text(json.dumps({'OPENAI_API_KEY': self.key}))
        (self.root / 'config.toml').write_text('model_provider="custom"\n[model_providers.custom]\nbase_url="https://existing.example.test/v1"\n')
        config = g.discover_api_config(self.root)
        self.assertEqual(config.credential_source, 'auth.json')
        self.assertEqual(config.endpoint_source, 'config.toml')
        self.assertEqual(config.api_key, self.key)
        report = g.config_report(self.root)
        self.assertTrue(report['api_mode']['available'])
        self.assertNotIn(self.key, json.dumps(report))

    def test_oauth_is_not_an_api_key(self):
        (self.root / 'auth.json').write_text(json.dumps({'tokens': {'access_token': self.key}}))
        with self.assertRaises(g.ConfigError):
            g.discover_api_config(self.root)

    def test_valid_image_preserves_bytes_and_hash(self):
        metadata = g.write_image(self.result, self.output)
        self.assertEqual(self.output.read_bytes(), self.png)
        self.assertEqual((metadata['width'], metadata['height']), (8, 6))
        self.assertEqual(metadata['sha256'], hashlib.sha256(self.png).hexdigest())
        with Image.open(self.output) as image:
            image.load()
        self.assertEqual(list(self.root.iterdir()), [self.output])

    def test_image_not_overwritten_without_force(self):
        self.output.write_bytes(b'existing-user-data')
        with self.assertRaises(g.ApiError) as error:
            g.write_image(self.result, self.output)
        self.assertEqual(error.exception.report['outcome'], 'generated')
        self.assertEqual(self.output.read_bytes(), b'existing-user-data')
        g.write_image(self.result, self.output, force=True)
        self.assertEqual(self.output.read_bytes(), self.png)

    def test_empty_invalid_base64_and_corrupt_images(self):
        payloads = [{}, {'data': []}, {'data': [{'b64_json': ''}]}, {'data': [{'b64_json': '%%%'}]}, {'data': [{'b64_json': base64.b64encode(self.png[:40]).decode()}]}]
        for payload in payloads:
            with self.subTest(payload=str(payload)[:30]), self.assertRaises(g.ApiError):
                g.write_image(payload, self.output)
        self.assertFalse(self.output.exists())

    def test_all_http_status_diagnostics(self):
        for status in HTTP_GUIDANCE:
            with self.subTest(status=status):
                error = upstream_error({'error': {'message': 'upstream detail'}}, status)
                self.assertEqual(error.report['http_status'], status)
                self.assertTrue(error.report['possible_cause'])
                self.assertTrue(error.report['suggested_action'])
                self.assertFalse(error.report['automatic_retry'])

    def test_http_200_business_failure_and_normal_success(self):
        for obj in ({'error': {'message': 'failed'}}, {'code': 503, 'message': 'no route'}, {'success': False}, {'status': 'failed'}):
            with self.subTest(obj=obj):
                self.assertIsNotNone(upstream_error(obj))
        self.assertIsNone(upstream_error({'code': 0, **self.result}))
        self.assertIsNone(upstream_error(self.result))

    def test_policy_refusal_code_and_text(self):
        errors = [
            {'error': {'code': 'content_policy_violation', 'message': 'blocked'}},
            {'error': {'message': '图像可能违反规范，请更换提示词'}},
            {'refusal': 'Cannot generate this image'},
            {'output': [{'content': [{'type': 'refusal', 'refusal': 'Content rejected'}]}]},
        ]
        for obj in errors:
            with self.subTest(obj=obj):
                error = upstream_error(obj)
                self.assertEqual(error.report['category'], 'content_policy_rejection')
                self.assertIn('停止所有模式切换', error.report['suggested_action'])
        self.assertIsNone(upstream_error({'data': [], 'message': '安全的图片内容'}))
        self.assertNotEqual(upstream_error({'error': {'code': 'image_generation_user_error', 'message': 'Invalid size'}}).report['category'], 'content_policy_rejection')

    def test_quota_vs_throttling_and_403(self):
        self.assertEqual(upstream_error({'error': {'code': 'insufficient_quota'}}, 429).report['category'], 'quota_exceeded')
        self.assertEqual(upstream_error({'error': {'message': 'too many requests'}}, 429).report['category'], 'rate_limit')
        self.assertEqual(upstream_error({'error': {'message': '额度不足'}}, 403).report['category'], 'quota_exceeded')
        self.assertEqual(upstream_error({'error': {'message': 'denied'}}, 403).report['category'], 'permission_error')

    def test_cloudflare_evidence_required(self):
        self.assertIn('尚无足够证据', upstream_error('timeout', 524).report['possible_cause'])
        self.assertIn('已连接源站', upstream_error('timeout', 524, {'cf-ray': 'example'}).report['possible_cause'])

    def test_redaction_before_truncation_and_html_omission(self):
        error = upstream_error({'error': {'message': self.key + ' x' * 1000}}, 401, secrets=(self.key,))
        self.assertNotIn(self.key, str(error))
        self.assertLessEqual(len(error.report['upstream_message']), 800)
        text = 'Authorization: Bearer TEST_ONLY_REDACTION_VALUE https://example.test/a?token=private&x=y'
        safe = redact(text)
        self.assertNotIn('TEST_ONLY_REDACTION_VALUE', safe)
        self.assertNotIn('private', safe)
        self.assertNotIn('private', upstream_error('<html>private</html>', 502).report['upstream_message'])

    def test_api_http_error_no_retry_no_key_echo(self):
        raw = json.dumps({'error': {'message': self.key}}).encode()
        opener = MagicMock()
        opener.open.side_effect = urllib.error.HTTPError('https://example.test', 401, 'Unauthorized', {}, io.BytesIO(raw))
        with patch.object(g.urllib.request, 'build_opener', return_value=opener), self.assertRaises(g.ApiError) as error:
            g.api_request('https://example.test/v1/images/generations', self.key, b'{}', 'application/json')
        self.assertNotIn(self.key, str(error.exception))
        self.assertEqual(opener.open.call_count, 1)

    def test_api_non_json_and_non_object(self):
        for raw, category in [(b'<html>error</html>', 'non_json_response'), (b'[]', 'invalid_response')]:
            with self.subTest(category=category), patch.object(g.urllib.request, 'build_opener', return_value=self.mock_response(raw)), self.assertRaises(g.ApiError) as error:
                g.api_request('https://example.test/v1', self.key, b'{}', 'application/json')
            self.assertEqual(error.exception.report['category'], category)

    def test_api_network_and_timeout(self):
        for exc, category in [(TimeoutError(), 'timeout'), (urllib.error.URLError(socket.timeout()), 'timeout'), (urllib.error.URLError('dns failure'), 'connection_error')]:
            opener = MagicMock()
            opener.open.side_effect = exc
            with self.subTest(category=category), patch.object(g.urllib.request, 'build_opener', return_value=opener), self.assertRaises(g.ApiError) as error:
                g.api_request('https://example.test/v1', self.key, b'{}', 'application/json')
            self.assertEqual(error.exception.report['category'], category)
            self.assertEqual(error.exception.report['outcome'], 'unknown')
            self.assertEqual(opener.open.call_count, 1)

    def test_cross_origin_redirect_blocked(self):
        req = urllib.request.Request('https://one.example.test/a', headers={'Authorization': 'Bearer ' + self.key})
        handler = g.SafeRedirectHandler()
        for target in ('https://two.example.test/a', 'http://one.example.test/a', 'https://one.example.test:8443/a'):
            with self.subTest(target=target), self.assertRaises(g.ApiError):
                handler.redirect_request(req, None, 302, 'Found', {}, target)
        allowed = handler.redirect_request(req, None, 302, 'Found', {}, 'https://one.example.test/b')
        self.assertEqual(allowed.get_header('Authorization'), 'Bearer ' + self.key)

    def test_image_url_download_has_no_api_authorization(self):
        with patch.object(g, 'request_bytes', return_value=(self.png, {})) as request:
            g.write_image({'data': [{'url': 'https://images.example.test/a?signature=synthetic'}]}, self.output)
        sent = request.call_args.args[0]
        self.assertIsNone(sent.get_header('Authorization'))

    def test_download_failure_is_delivery_not_generation_failure(self):
        with patch.object(g, 'request_bytes', side_effect=g.ApiError('download failed')), self.assertRaises(g.ApiError) as error:
            g.write_image({'data': [{'url': 'https://images.example.test/a'}]}, self.output)
        self.assertEqual(error.exception.report['outcome'], 'delivery_failed')
        self.assertIn('不重新生成', error.exception.report['suggested_action'])

    def test_recover_only_exact_response_call_no_network(self):
        session = self.root / 'session.jsonl'
        fake = {'type': 'message', 'payload': {'type': 'image_generation_call', 'id': 'chosen', 'result': '%%%'}}
        other = {'type': 'response_item', 'payload': {'type': 'image_generation_call', 'id': 'other', 'result': '%%%'}}
        correct = {'type': 'response_item', 'payload': {'type': 'image_generation_call', 'id': 'chosen', 'status': 'completed', 'result': self.result['data'][0]['b64_json']}}
        session.write_text('\n'.join(map(json.dumps, [fake, other, correct])) + '\n{"partial":')
        before = session.read_bytes()
        with patch.object(g, 'api_request') as request:
            code, out, _ = self.cli(['recover-native', '--session-file', str(session), '--call-id', 'chosen', '--out', str(self.output)])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)['sha256'], hashlib.sha256(self.png).hexdigest())
        self.assertEqual(session.read_bytes(), before)
        request.assert_not_called()

    def test_unknown_native_result_is_not_retried(self):
        session = self.root / 'session.jsonl'
        session.write_text('')
        with patch.object(g, 'api_request') as request:
            code, _, err = self.cli(['recover-native', '--session-file', str(session), '--call-id', 'missing', '--out', str(self.output)])
        self.assertEqual(code, 1)
        self.assertIn('native_result_unknown', err)
        request.assert_not_called()

    def test_native_failed_refusal(self):
        session = self.root / 'session.jsonl'
        session.write_text(json.dumps({'type': 'response_item', 'payload': {'type': 'image_generation_call', 'id': 'blocked', 'status': 'failed', 'error': {'code': 'content_policy_violation'}}}))
        with self.assertRaises(g.ApiError) as error:
            g.recover_native(session, 'blocked', self.output)
        self.assertEqual(error.exception.report['category'], 'content_policy_rejection')

    def test_cli_fallback_success_and_no_existing_config_reads(self):
        g.configure_fallback({'api_key': self.key})
        with patch.object(g, 'discover_api_config', side_effect=AssertionError('Do not read existing config')), patch.object(g, 'api_request', return_value=self.result) as request:
            code, out, err = self.cli(['generate', '--config-source', 'fallback', '--prompt', 'test', '--out', str(self.output)])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)['mode'], 'fallback')
        self.assertEqual(request.call_count, 1)
        self.assertNotIn(self.key, out + err)

    def test_cli_safety_error_does_not_switch_or_retry(self):
        g.configure_fallback({'api_key': self.key})
        failure = upstream_error({'error': {'code': 'content_policy_violation'}})
        with patch.object(g, 'api_request', side_effect=failure) as request:
            code, _, err = self.cli(['generate', '--config-source', 'fallback', '--prompt', 'test', '--out', str(self.output)])
        self.assertEqual(code, 1)
        self.assertIn('content_policy_rejection', err)
        self.assertEqual(request.call_count, 1)

    def test_dependency_preflight_precedes_billable_request(self):
        with patch.object(g, 'image_runtime', side_effect=g.ConfigError('Pillow missing')), patch.object(g, 'api_request') as request:
            code, _, _ = self.cli(['generate', '--prompt', 'test', '--out', str(self.output)])
        self.assertEqual(code, 2)
        request.assert_not_called()

    def test_edit_request_contract_retained(self):
        self.output.write_bytes(self.png)
        body, content_type = g.multipart_body('test prompt', [self.output], 'auto', 'medium')
        self.assertIn(b'gpt-image-2.5-flare', body)
        self.assertIn(self.png, body)
        self.assertIn('multipart/form-data', content_type)
        self.assertEqual(json.loads(g.json_body('test', 'auto', 'medium'))['n'], 1)

    def test_broken_existing_config_does_not_hide_fallback(self):
        (self.root / 'config.toml').write_text('not valid toml !!!')
        g.configure_fallback({'api_key': self.key})
        report = g.config_report(self.root)
        self.assertFalse(report['api_mode']['available'])
        self.assertTrue(report['fallback_mode']['available'])
        self.assertNotIn(self.key, json.dumps(report))

    def test_reject_full_request_path(self):
        for suffix in ('/v1/images/generations', '/v1/images/edits', '/v1/responses'):
            with self.subTest(suffix=suffix), self.assertRaises(g.ConfigError):
                g.validate_fallback({'base_url': 'https://example.test' + suffix, 'api_key': self.key})

    def test_plain_text_200_policy_refusal(self):
        with patch.object(g.urllib.request, 'build_opener', return_value=self.mock_response('图像可能违反规范，请更换提示词'.encode())), self.assertRaises(g.ApiError) as error:
            g.api_request('https://example.test/v1', self.key, b'{}', 'application/json')
        self.assertEqual(error.exception.report['category'], 'content_policy_rejection')

    def test_cli_oversized_configuration_is_not_saved(self):
        code, out, err = self.cli(['configure-fallback'], json.dumps({'api_key': self.key, 'extra': 'a' * 17000}))
        self.assertEqual(code, 2)
        self.assertFalse(self.config.exists())
        self.assertNotIn(self.key, out + err)

    def test_cli_error_json_stays_parseable_and_secret_safe(self):
        g.configure_fallback({'api_key': self.key})
        failure = upstream_error({'error': {'message': 'Authorization: Bearer ' + self.key}}, 401)
        with patch.object(g, 'api_request', side_effect=failure):
            code, out, err = self.cli(['generate', '--config-source', 'fallback', '--prompt', 'test', '--out', str(self.output)])
        self.assertEqual(code, 1)
        self.assertNotIn(self.key, out + err)
        report = json.loads(err.split(': ', 1)[1])
        self.assertEqual(report['http_status'], 401)


    def test_package_excludes_local_credentials_and_rollback(self):
        for name in package_skill.PUBLIC_FILES:
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('public fixture')
        g.configure_fallback({'api_key': self.key})
        (self.root / '.rollback').mkdir()
        (self.root / '.rollback' / 'old.zip').write_bytes(b'old')
        (self.root / '.fallback-config.local.json.synthetic.tmp').write_text(self.key)
        output = self.root / 'package.zip'
        package_skill.package(self.root, output)
        with zipfile.ZipFile(output) as archive:
            self.assertEqual(len(archive.namelist()), len(package_skill.PUBLIC_FILES))
            for name in archive.namelist():
                self.assertNotIn(self.key.encode(), archive.read(name))
                self.assertNotIn('fallback-config.local', name)
                self.assertNotIn('.rollback', name)

    def test_default_and_selectable_image_models(self):
        self.assertEqual(g.DEFAULT_MODEL, 'gpt-image-2.5-flare')
        self.assertEqual(set(g.SUPPORTED_MODELS), {
            'gpt-image-2.5-flare', 'gpt-image-2.5-sunburst', 'gpt-image-2.5', 'gpt-image-2', 'gpt-image-2-2026-04-21', 'gemini-nano-banana-2.1'
        })
        for model in g.SUPPORTED_MODELS:
            with self.subTest(model=model):
                if model == g.GEMINI_MODEL:
                    payload = json.loads(g.gemini_json_body('test', [], None, None, None, False, False))
                    self.assertEqual(payload['generationConfig']['responseModalities'], ['TEXT', 'IMAGE'])
                else:
                    payload = json.loads(g.json_body('test', 'auto', 'medium', model))
                    self.assertEqual(payload['model'], model)

    def test_gpt_image_2_5_is_selectable_but_not_default(self):
        self.assertEqual(g.DEFAULT_MODEL, 'gpt-image-2.5-flare')
        payload = json.loads(g.json_body('test', 'auto', 'medium', 'gpt-image-2.5'))
        self.assertEqual(payload['model'], 'gpt-image-2.5')

    def test_model_specific_quality_validation(self):
        for model in ('gpt-image-2.5-flare', 'gpt-image-2.5-sunburst'):
            self.assertEqual(json.loads(g.json_body('test', 'auto', 'max', model))['quality'], 'max')
        with self.assertRaises(g.ConfigError):
            g.json_body('test', 'auto', 'max', 'gpt-image-2')

    def test_cli_selected_model_reaches_request_and_report(self):
        with (
            patch.object(g, 'discover_api_config', return_value=g.ApiConfig(
                'https://example.test/v1', self.key, 'test', 'test')),
            patch.object(g, 'api_request', return_value=self.result) as request,
        ):
            code, out, err = self.cli([
                'generate', '--model', 'gpt-image-2.5-sunburst', '--prompt', 'test',
                '--out', str(self.output)
            ])
        self.assertEqual((code, err), (0, ''))
        sent = json.loads(request.call_args.args[2])
        self.assertEqual(sent['model'], 'gpt-image-2.5-sunburst')
        self.assertEqual(json.loads(out)['model'], 'gpt-image-2.5-sunburst')
        self.assertEqual(json.loads(out)['user_status'], '图片生成请求已发送，使用模型gpt-image-2.5-sunburst正在绘图中，请稍后 ')


    def test_request_defaults_and_sunburst_quality(self):
        prompt, model, quality, size, preset, background, output_format = g.resolve_request_options('test', None, None, None, None)
        self.assertEqual((prompt, model, quality, size, preset, background, output_format),
                         ('test', 'gpt-image-2.5-flare', 'medium', 'auto', 'auto', 'auto', 'png'))
        _, model, quality, _, _, _, _ = g.resolve_request_options(
            'test', 'gpt-image-2.5-sunburst', None, None, None)
        self.assertEqual((model, quality), ('gpt-image-2.5-sunburst', 'high'))

    def test_preset_defaults_and_explicit_overrides(self):
        _, model, quality, size, preset, _, _ = g.resolve_request_options(
            'custom prompt', 'gpt-image-2.5', 'xhigh', '1024x1024', 'fast')
        self.assertEqual((model, quality, size, preset),
                         ('gpt-image-2.5', 'xhigh', '1024x1024', 'fast'))
        prompt, model, quality, size, preset, background, output_format = g.resolve_request_options(
            None, None, None, None, 'benchmark-t2i')
        self.assertIn('PROJECT SUNBURST', prompt)
        self.assertEqual((model, quality, size, preset),
                         ('gpt-image-2.5-sunburst', 'high', 'auto', 'benchmark-t2i'))

    def test_run_without_image_is_single_generate_request(self):
        with (
            patch.object(g, 'config_report', side_effect=AssertionError('No preflight config-check')),
            patch.object(g, 'discover_api_config', return_value=g.ApiConfig(
                'https://example.test/v1', self.key, 'test', 'test')),
            patch.object(g, 'api_request', return_value=self.result) as request,
        ):
            code, out, err = self.cli(['run', '--prompt', 'test', '--out', str(self.output)])
        self.assertEqual((code, err), (0, ''))
        report = json.loads(out)
        self.assertEqual((report['operation'], report['model'], report['quality'], report['preset']),
                         ('generate', 'gpt-image-2.5-flare', 'medium', 'auto'))
        self.assertTrue(request.call_args.args[0].endswith('/images/generations'))
        self.assertEqual(request.call_count, 1)

    def test_run_with_image_is_single_edit_request(self):
        source = self.root / 'source.png'
        source.write_bytes(self.png)
        with (
            patch.object(g, 'discover_api_config', return_value=g.ApiConfig(
                'https://example.test/v1', self.key, 'test', 'test')),
            patch.object(g, 'api_request', return_value=self.result) as request,
        ):
            code, out, err = self.cli([
                'run', '--image', str(source), '--prompt', 'change background',
                '--out', str(self.output)
            ])
        self.assertEqual((code, err), (0, ''))
        report = json.loads(out)
        self.assertEqual(report['operation'], 'edit')
        self.assertTrue(request.call_args.args[0].endswith('/images/edits'))
        self.assertEqual(request.call_count, 1)

    def test_fast_path_document_contract(self):
        root = Path(__file__).resolve().parents[1]
        skill = (root / 'SKILL.md').read_text(encoding='utf-8')
        old_workflow = (root / 'references' / 'workflow.md').read_text(encoding='utf-8')
        self.assertIn('图片生成请求已发送，使用模型{MODEL_ID}正在绘图中，请稍后', skill)
        self.assertIn('图片生成进度：使用模型{MODEL_ID}，已等待{SECONDS}秒，当前状态：{OBSERVED_STATUS}', old_workflow)
        self.assertIn('每 30 秒固定检查并播报一次', old_workflow)
        self.assertIn('原始报错、准确中文翻译和解决建议', old_workflow)
        self.assertIn('错误码/类别：{HTTP_STATUS_OR_UPSTREAM_CODE} / {CATEGORY}', old_workflow)
        self.assertIn('原始报错（脱敏后）：{RAW_ERROR}', old_workflow)
        self.assertIn('中文翻译：{TRANSLATION}', old_workflow)
        self.assertIn('解决建议：{SUGGESTION}', old_workflow)
        self.assertNotIn('每 60 秒检查一次', skill)
        self.assertNotIn('只有状态变化才播报', skill)
        monitoring = (root / 'references' / 'monitoring.md').read_text(encoding='utf-8')
        errors = (root / 'references' / 'errors.md').read_text(encoding='utf-8')
        models = (root / 'references' / 'models.md').read_text(encoding='utf-8')
        self.assertIn('在 30、60、90 秒等时间点固定检查并播报一次', monitoring)
        self.assertIn('状态不变也必须播报', monitoring)
        self.assertIn('原始报错（脱敏后）', errors)
        self.assertIn('中文翻译：{TRANSLATION}', errors)
        self.assertIn('解决建议：{SUGGESTION}', errors)
        self.assertIn('用户显式模型 > preset 模型 > 默认模型', models)
        self.assertIn('config-check', skill)
        self.assertIn('不得把恢复当作生成、不得重复生图', old_workflow)
        self.assertIn('native_delivery.py prepare', skill)
        self.assertIn('artifact_ready', skill)
        self.assertIn('references/recovery.md', skill)
        self.assertTrue((root / 'references' / 'delivery.md').is_file())
        self.assertTrue((root / 'references' / 'recovery.md').is_file())
        self.assertIn('references/monitoring.md', package_skill.PUBLIC_FILES)


    def test_config_report_lists_fast_presets(self):
        report = g.existing_config_report(self.root)
        self.assertEqual(report['available_presets'], list(g.PRESET_OPTIONS))
        self.assertIn('benchmark-t2i', report['available_presets'])

    def test_transparent_background_json_contract(self):
        payload = json.loads(g.json_body(
            'isolated mascot', '1024x1024', 'high', 'gpt-image-2', 'transparent', 'png'
        ))
        self.assertEqual(payload['background'], 'transparent')
        self.assertEqual(payload['output_format'], 'png')

    def test_transparent_background_defaults_to_png(self):
        values = g.resolve_request_options('isolated mascot', 'gpt-image-2', 'high', None, 'transparent')
        self.assertEqual(values[-2:], ('transparent', 'png'))
        self.assertEqual(g.default_output('gpt-image-2', 'webp').suffix, '.webp')

    def test_transparent_jpeg_is_rejected_before_network(self):
        with self.assertRaises(g.ConfigError):
            g.json_body('isolated mascot', 'auto', 'high', 'gpt-image-2', 'transparent', 'jpeg')

    def test_transparent_response_requires_real_alpha_pixels(self):
        opaque = io.BytesIO()
        Image.new('RGBA', (8, 6), (20, 40, 80, 255)).save(opaque, format='PNG')
        with self.assertRaises(g.ApiError) as error:
            g.save_image_bytes(opaque.getvalue(), self.output, require_alpha=True)
        self.assertEqual(error.exception.report['category'], 'invalid_transparency')
        self.assertFalse(self.output.exists())

    def test_transparent_response_reports_alpha_metadata(self):
        alpha = io.BytesIO()
        image = Image.new('RGBA', (8, 6), (20, 40, 80, 255))
        image.putpixel((0, 0), (20, 40, 80, 0))
        image.save(alpha, format='PNG')
        report = g.save_image_bytes(alpha.getvalue(), self.output, require_alpha=True)
        self.assertTrue(report['has_alpha'])
        self.assertEqual(report['alpha_min'], 0)
        self.assertEqual(report['image_mode'], 'RGBA')

    def test_unspecified_transparency_preserves_default_model(self):
        values = g.resolve_request_options('isolated mascot', None, None, None, None, 'transparent', None)
        self.assertEqual(values[1], 'gpt-image-2.5-flare')
        self.assertEqual(values[-2:], ('transparent', 'png'))

    def test_explicit_transparency_model_is_preserved(self):
        values = g.resolve_request_options('isolated mascot', 'gpt-image-2.5-flare', 'medium', None, None, 'transparent', 'webp')
        self.assertEqual(values[1], 'gpt-image-2.5-flare')
        self.assertEqual(values[-2:], ('transparent', 'webp'))


    def test_both_image_2_5_models_preserve_transparent_contract(self):
        for model, quality in (("gpt-image-2.5-flare", "medium"), ("gpt-image-2.5-sunburst", "high")):
            with self.subTest(model=model):
                values = g.resolve_request_options("isolated mascot", model, quality, "1024x1024", None, "transparent", "png")
                self.assertEqual(values[1], model)
                self.assertEqual(values[-2:], ("transparent", "png"))
                payload = json.loads(g.json_body(values[0], values[3], values[2], values[1], values[-2], values[-1]))
                self.assertEqual(payload["model"], model)
                self.assertEqual(payload["background"], "transparent")
                self.assertEqual(payload["output_format"], "png")

    def test_skill_entrypoint_exposes_2_5_transparency_and_update_source(self):
        root = Path(__file__).resolve().parents[1]
        skill = (root / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("gpt-image-2.5-flare", skill)
        self.assertIn("gpt-image-2.5-sunburst", skill)
        self.assertIn("background=transparent", skill)
        self.assertIn("https://github.com/Acreg/codex_skills_image-2", skill)
        self.assertEqual((root / "VERSION").read_text(encoding="utf-8").strip(), g.VERSION)

    def test_v4_name_usage_endpoint_and_model_guide_contract(self):
        root = Path(__file__).resolve().parents[1]
        skill = (root / "SKILL.md").read_text(encoding="utf-8")
        yaml = (root / "agents" / "openai.yaml").read_text(encoding="utf-8")
        models = (root / "references" / "models.md").read_text(encoding="utf-8")
        self.assertIn("name: aa-onemini-image-generation", skill)
        self.assertIn('display_name: "GPT-image2图片生成工具"', yaml)
        self.assertIn("https://api.onemini.top/v1", skill)
        self.assertIn("图片生成工作站", skill)
        self.assertIn("2 分钟", skill)
        for model in g.SUPPORTED_MODELS:
            self.assertIn(model, skill)
            self.assertIn(model, models)
        self.assertEqual((root / "VERSION").read_text(encoding="utf-8").strip(), "4.1.3")
        self.assertEqual(g.VERSION, "4.1.3")

if __name__ == '__main__':
    unittest.main()
