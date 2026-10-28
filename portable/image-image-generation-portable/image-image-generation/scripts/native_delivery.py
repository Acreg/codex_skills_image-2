"""Offline current-turn image delivery. Never calls an image API or reads credentials."""
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import uuid

import generate_image as g


def thread_id():
    values = {os.environ[k] for k in ('CODEX_THREAD_ID', 'CODEX_SESSION_ID') if os.environ.get(k)}
    if len(values) != 1:
        raise g.ConfigError('当前任务标识缺失或冲突；不搜索其他任务')
    value = values.pop()
    try:
        uuid.UUID(value)
    except ValueError as exc:
        raise g.ConfigError('当前任务标识不是有效 UUID') from exc
    return value


def read_calls(session, expected_thread):
    # Validate ownership before accepting any image; ignore instructions and user attachments.
    calls = {}
    verified = False
    with session.open(encoding='utf-8-sig') as stream:
        for line in stream:
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue  # The app may still be appending the last record.
            if not isinstance(record, dict):
                continue
            item = record.get('payload')
            if not isinstance(item, dict):
                continue
            if record.get('type') == 'session_meta':
                if item.get('id') != expected_thread:
                    raise g.ConfigError('会话元数据与当前任务不匹配')
                verified = True
            if verified and record.get('type') == 'response_item' and item.get('type') == 'image_generation_call':
                call_id = item.get('id')
                if isinstance(call_id, str):
                    if item.get('result') or not calls.get(call_id, {}).get('result'):
                        calls[call_id] = item
    if not verified:
        raise g.ConfigError('会话缺少当前任务身份验证信息')
    return calls


def current_sessions(current):
    root = (g.codex_home() / 'sessions').resolve()
    # A continued/forked desktop task may have multiple JSONL segments containing the
    # same verified session id. Bind all matching segments and use the before/after
    # call-id set; never pick one by mtime or by "latest file".
    matches = sorted(path.resolve() for path in root.rglob(f'*-{current}*.jsonl'))
    if not matches:
        raise g.ConfigError('未定位当前任务会话；不搜索其他任务')
    for session in matches:
        if not session.is_relative_to(root):
            raise g.ConfigError('会话路径超出 sessions 目录')
        read_calls(session, current)  # Validate session metadata before binding it.
    return matches


def combined_calls(sessions, current):
    combined = {}
    for session in sessions:
        for call_id, item in read_calls(session, current).items():
            if item.get('result') or not combined.get(call_id, {}).get('result'):
                combined[call_id] = item
    return combined


def prepare(state_path, output=None):
    g.image_runtime()  # Check the local decoder before the potentially billable native call.
    current = thread_id()
    sessions = current_sessions(current)
    calls = combined_calls(sessions, current)
    # Native results use the current project output directory by default; session data remains recovery-only.
    output = (output or g.default_output(g.DEFAULT_MODEL, "png")).expanduser().resolve()
    state_path = state_path.expanduser().resolve()
    if output == state_path or output.exists() or state_path.exists():
        raise g.ConfigError('状态或输出路径已存在/冲突；生图前选择新路径，不覆盖')
    state = {'thread_id': current, 'session_files': [str(path) for path in sessions], 'before_ids': sorted(calls), 'output': str(output)}
    g.atomic_write(state_path, (json.dumps(state, ensure_ascii=False) + '\n').encode('utf-8'))
    return {'status': 'prepared', 'state': str(state_path), 'next': 'call_native_once_then_deliver'}


def deliver(state_path, call_id=None, wait_seconds=2, chat_visible=False):
    current = thread_id()
    state = json.loads(state_path.read_text(encoding='utf-8'))
    if state.get('thread_id') != current:
        raise g.ConfigError('交付状态不属于当前任务')
    sessions = current_sessions(current)
    current_paths = {str(path) for path in sessions}
    recorded_paths = set(state.get('session_files') or ([state['session_file']] if state.get('session_file') else []))
    if not recorded_paths or not recorded_paths.issubset(current_paths):
        raise g.ConfigError('交付状态中的会话路径与当前任务不一致')
    baseline = set(state['before_ids'])
    if call_id is not None and call_id in baseline:
        raise g.ConfigError('指定调用是准备阶段之前的旧图，不属于本次生成')
    item = None
    for attempt in range(2):
        calls = combined_calls(sessions, current)
        candidates = {key: value for key, value in calls.items() if key not in baseline}
        if call_id is not None:
            candidates = {key: value for key, value in candidates.items() if key == call_id}
        if len(candidates) > 1:
            raise g.ConfigError('本次出现多个图片调用；须指定已确认的 --call-id，不猜测')
        item = next(iter(candidates.values()), None)
        if item and (item.get('result') or item.get('status') == 'failed'):
            break
        if attempt == 0:
            time.sleep(wait_seconds)  # One bounded local recheck, never a generation retry.
    if not item or not item.get('result'):
        if item and item.get('status') == 'failed':
            error = g.upstream_error(item)
            if error:
                raise error
        raise g.ApiError('未找到本次可恢复的图片数据，未重新生成', category='native_result_unknown')
    data = g.decode_image(item['result'])
    output = Path(state['output'])
    reused = output.exists()
    if reused:
        # Rerunning delivery may reuse this exact artifact, never an unrelated existing file.
        if output.read_bytes() != data:
            raise g.ConfigError('输出位置已有不同内容；保留原文件，不覆盖或重新生成')
        with g.image_runtime().open(output) as image:
            image.load()
            metadata = {'width': image.width, 'height': image.height, 'image_format': image.format,
                        'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest(),
                        'markdown': g.image_markdown(output)}
    else:
        metadata = g.save_image_bytes(data, output)
    return {
        'status': 'user_delivered' if chat_visible else 'artifact_ready',
        'delivery_state': 'CHAT_RENDER_VERIFIED' if chat_visible else 'CHAT_RENDER_UNVERIFIED',
        'call_id': item['id'], 'output': str(output), 'reused': reused,
        'artifact_saved': True, 'client_render_verified': bool(chat_visible), **metadata,
    }


def main():
    parser = g.SafeArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('prepare', 'deliver'))
    parser.add_argument('--state', type=Path, required=True)
    parser.add_argument('--out', type=Path, help='项目 output/imagegen 路径；省略时自动生成唯一 PNG')
    parser.add_argument('--call-id')
    parser.add_argument('--chat-visible', action='store_true', help='Mark only after observing a visible image attachment in this reply')
    args = parser.parse_args()
    try:
        if args.command == 'prepare':
            if args.out is None:
                raise g.ConfigError('prepare 需要 --out')
            report = prepare(args.state, args.out)
        else:
            report = deliver(args.state, args.call_id, chat_visible=args.chat_visible)
        print(json.dumps(report, ensure_ascii=False))
        return 0
    except g.SkillError as exc:
        print(json.dumps(exc.report, ensure_ascii=False), file=sys.stderr)
        return 2 if isinstance(exc, g.ConfigError) else 1
    except (OSError, ValueError, KeyError, TypeError):
        print(json.dumps({'status': 'delivery_failed', 'message': '本地交付状态不可用；保留原记录，不重新生成'}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
