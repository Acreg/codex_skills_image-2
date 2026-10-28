#!/usr/bin/env python3
"""Image skill v4.0: one-command generation/edit, direct project output, and exceptional recovery.

Mode switching belongs to SKILL.md; this CLI never retries or calls another provider.
"""

from __future__ import annotations

import argparse
import base64
import json
import hashlib
import io
import socket
import tempfile
import mimetypes
import os
import secrets
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from image_errors import ApiError, ConfigError, SkillError, redact, upstream_error

VERSION = "4.1.3"
DEFAULT_MODEL = "gpt-image-2.5-flare"
GEMINI_MODEL = "gemini-nano-banana-2.1"
GEMINI_IMAGE_SIZES = ("1K", "2K", "4K")
GEMINI_ASPECT_RATIOS = ("1:1", "1:4", "1:8", "2:3", "3:2", "3:4", "4:1", "4:3", "4:5", "5:4", "8:1", "9:16", "16:9", "21:9")
SUPPORTED_MODELS = (
    "gpt-image-2.5-flare",
    "gpt-image-2.5-sunburst",
    "gpt-image-2.5",
    "gpt-image-2",
    "gpt-image-2-2026-04-21",
    GEMINI_MODEL,
)
MODEL_QUALITIES = {
    "gpt-image-2.5-flare": frozenset(("auto", "low", "medium", "high", "xhigh", "max")),
    "gpt-image-2.5-sunburst": frozenset(("auto", "low", "medium", "high", "xhigh", "max")),
    "gpt-image-2.5": frozenset(("auto", "low", "medium", "high", "xhigh", "max")),
    "gpt-image-2": frozenset(("auto", "low", "medium", "high")),
    "gpt-image-2-2026-04-21": frozenset(("auto", "low", "medium", "high")),
}
MODEL = DEFAULT_MODEL  # Backward-compatible public constant.
DEFAULT_QUALITY = "medium"
DEFAULT_SIZE = "auto"
DEFAULT_BACKGROUND = "auto"
DEFAULT_OUTPUT_FORMAT = "png"
BACKGROUND_OPTIONS = ("auto", "transparent", "opaque")
OUTPUT_FORMATS = ("png", "jpeg", "webp")
OUTPUT_SUFFIXES = {"png": ".png", "jpeg": ".jpeg", "webp": ".webp"}
BENCHMARK_T2I_PROMPT = (
    "横版电影级科幻摄影：黄昏的红色峡谷太阳观测站，中央金色环形日冕装置产生清晰放射光，"
    "前景三名穿白色科研服的人物，左侧全息太阳图，右侧机械臂与反射镜阵列，明确前中后景、"
    "真实光影和精密材质。画面仅出现三行清晰英文：PROJECT SUNBURST；LIGHT, MEASURED.；"
    "09 SEPTEMBER 2026。无水印、无额外文字、人物结构自然，成品级。"
)
PRESET_OPTIONS = {
    "auto": {},
    "fast": {"model": "gpt-image-2.5-flare", "quality": "medium", "size": "auto"},
    "final": {"model": "gpt-image-2.5-sunburst", "quality": "high", "size": "auto"},
    "text-heavy": {"model": "gpt-image-2.5-sunburst", "quality": "high", "size": "auto"},
    "benchmark-t2i": {
        "model": "gpt-image-2.5-sunburst", "quality": "high", "size": "auto",
        "prompt": BENCHMARK_T2I_PROMPT,
    },
    "transparent": {"background": "transparent", "output_format": "png"},
}
DEFAULT_BASE_URL = "https://api.openai.com/v1"


SKILL_ROOT = Path(__file__).resolve().parent.parent
FALLBACK_PATH = SKILL_ROOT / "fallback-config.local.json"
FALLBACK_BASE_URL = "https://api.openai.com"
GEMINI_CONFIG_PATH = SKILL_ROOT / "gemini-config.local.json"
GEMINI_DEFAULT_BASE_URL = "https://api.onemini.top/v1beta"
SKILL_ENV_PATH = SKILL_ROOT / ".env"
SKILL_ENV_KEYS = frozenset(("OPENAI_API_KEY", "OPENAI_BASE_URL", "GEMINI_API_KEY", "GEMINI_BASE_URL"))


@dataclass(frozen=True)
class ApiConfig:
    base_url: str
    api_key: str = field(repr=False)
    endpoint_source: str
    credential_source: str
    provider_name: str | None = None


def codex_home() -> Path:
    return Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex").expanduser()


def read_toml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        import tomllib
    except ModuleNotFoundError as exc:
        raise ConfigError("Python 3.11+ is required for TOML parsing") from exc
    try:
        value = tomllib.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ConfigError(f"Unable to read Codex config: {path}") from exc
    return value if isinstance(value, dict) else {}


def read_skill_env() -> dict[str, str]:
    """Read the local Skill .env directly, without modifying process environment."""
    if not SKILL_ENV_PATH.is_file():
        return {}
    try:
        lines = SKILL_ENV_PATH.read_text(encoding="utf-8-sig").splitlines()
    except OSError as exc:
        raise ConfigError("无法读取 Skill 根目录 .env") from exc
    values: dict[str, str] = {}
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise ConfigError(".env 配置格式错误；请使用 KEY = \"value\"")
        name, value = line.split("=", 1)
        name, value = name.strip(), value.strip()
        if name not in SKILL_ENV_KEYS:
            continue
        if value.startswith(('"', "'")):
            if len(value) < 2 or value[-1] != value[0]:
                raise ConfigError(".env 字符串引号不完整")
            value = value[1:-1]
        values[name] = value
    return values


def config_base_url(home: Path) -> tuple[str | None, str | None]:
    config = read_toml(home / "config.toml")
    provider_name = config.get("model_provider")
    providers = config.get("model_providers", {})
    if not isinstance(provider_name, str) or not isinstance(providers, dict):
        return None, None
    provider = providers.get(provider_name, {})
    if not isinstance(provider, dict):
        return None, provider_name
    base_url = provider.get("base_url")
    if isinstance(base_url, str) and base_url.strip():
        return base_url.strip(), provider_name
    return None, provider_name


def auth_file_key(home: Path) -> str | None:
    path = home / "auth.json"
    if not path.is_file():
        return None
    try:
        auth = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ConfigError(f"Unable to read Codex auth file: {path}") from exc
    value = auth.get("OPENAI_API_KEY") if isinstance(auth, dict) else None
    return value.strip() if isinstance(value, str) and value.strip() else None


def normalize_base_url(value: str, *, https_only: bool = False) -> str:
    if not isinstance(value, str):
        raise ConfigError("API 根地址必须为字符串")
    url = value.strip().rstrip("/")
    try:
        parsed = urllib.parse.urlsplit(url)
        allowed = {"https"} if https_only else {"http", "https"}
        valid = parsed.scheme in allowed and bool(parsed.hostname) and parsed.port != 0
    except ValueError:
        valid = False
    if not valid:
        raise ConfigError("API 根地址必须为有效 HTTPS 地址" if https_only else "API 根地址必须为有效 HTTP(S) 地址")
    if parsed.username is not None or parsed.password is not None or parsed.query or parsed.fragment:
        raise ConfigError("API 根地址不能包含凭证、查询参数或片段")
    if "\\" in url or any(ord(ch) < 33 for ch in url):
        raise ConfigError("API 根地址不能包含空白或反斜杠")
    if parsed.path.rstrip("/").lower().endswith(("/images/generations", "/images/edits", "/responses")):
        raise ConfigError("请提供网站或 /v1 根地址，不要提供完整请求接口路径")
    return url if parsed.path.rstrip("/").lower().endswith("/v1") else f"{url}/v1"


def discover_api_config(home: Path) -> ApiConfig:
    values = read_skill_env()
    local_key = values.get("OPENAI_API_KEY", "").strip()
    codex_key = auth_file_key(home) if not local_key else None
    environment_key = os.environ.get("OPENAI_API_KEY", "").strip()
    api_key = local_key or codex_key or environment_key
    credential_source = ".env" if local_key else "auth.json" if codex_key else "environment" if environment_key else "missing"

    configured_url, provider_name = config_base_url(home)
    local_url = values.get("OPENAI_BASE_URL", "").strip()
    environment_url = os.environ.get("OPENAI_BASE_URL", "").strip()
    base_url = local_url or configured_url or environment_url or DEFAULT_BASE_URL
    endpoint_source = ".env" if local_url else "config.toml" if configured_url else "environment" if environment_url else "official-default"

    if not api_key:
        raise ConfigError(
            "No explicit API key found. Set OPENAI_API_KEY or provide "
            "OPENAI_API_KEY in Codex auth.json. Codex Desktop native image "
            "generation can still work without API mode."
        )

    return ApiConfig(
        base_url=normalize_base_url(base_url),
        api_key=api_key,
        endpoint_source=endpoint_source,
        credential_source=credential_source,
        provider_name=provider_name,
    )


def endpoint_host(base_url: str) -> str:
    return urllib.parse.urlparse(base_url).hostname or "unknown"


def origin(url: str) -> tuple[str, str | None, int]:
    parsed = urllib.parse.urlsplit(url)
    return parsed.scheme.lower(), parsed.hostname, parsed.port or (443 if parsed.scheme == "https" else 80)


class SafeRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # urllib may copy Authorization across hosts; stop before building that request.
        if origin(req.full_url) != origin(newurl):
            raise ApiError("已阻止跨源重定向", category="unsafe_redirect", http_status=code,
                           cause="重定向到不同来源可能泄露凭证", action="核对正确的 API 地址后再操作")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def request_bytes(request: urllib.request.Request, api_key: str = "") -> tuple[bytes, Any]:
    try:
        with urllib.request.build_opener(SafeRedirectHandler()).open(request, timeout=300) as response:
            return response.read(), response.headers
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            payload = raw
        raise upstream_error(payload, exc.code, exc.headers, (api_key,)) or ApiError("上游 HTTP 错误") from exc
    except (TimeoutError, socket.timeout) as exc:
        raise ApiError("等待请求结果超时", category="timeout", cause="本次请求结果未知，可能已生成或计费",
                       action="先检查已有产物与调用记录，不自动重发") from exc
    except urllib.error.URLError as exc:
        if isinstance(exc.reason, (TimeoutError, socket.timeout)):
            raise ApiError("网络等待超时", category="timeout", cause="请求结果未知，可能已计费",
                           action="检查已有产物和调用记录，不自动重发") from exc
        raise ApiError(str(exc.reason), category="connection_error", cause="连接、DNS、TLS 或代理链路异常",
                       action="检查网络及请求记录；不能确定请求未送达时不重发", secrets=(api_key,)) from exc
    except (OSError, ValueError) as exc:
        raise ApiError(str(exc), category="connection_error", cause="连接或读取响应失败，本次结果可能未知",
                       action="核对网络与已有产物，不自动重发", secrets=(api_key,)) from exc


def api_request(url: str, api_key: str, body: bytes | None = None,
                content_type: str = "application/json", *, method: str = "POST") -> dict[str, Any]:
    request = urllib.request.Request(url, data=body, method=method, headers={
        "Authorization": f"Bearer {api_key}", "Content-Type": content_type,
        "Accept": "application/json", "User-Agent": f"codex-image-skill/{VERSION}",
    })
    payload, headers = request_bytes(request, api_key)
    try:
        result = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        error = upstream_error(payload.decode("utf-8", errors="replace"), 200, headers, (api_key,))
        if error:
            raise error from exc
        raise ApiError("上游返回非 JSON 响应（可能为 HTML 错误页），未输出页面内容", category="non_json_response",
                       http_status=200, cause="接口、反代或上游响应异常", action="核对地址与调用记录，不自动重试") from exc
    if not isinstance(result, dict):
        raise ApiError("上游 JSON 不是预期对象", category="invalid_response", http_status=200)
    error = upstream_error(result, 200, headers, (api_key,))
    if error:
        raise error
    return result


def gemini_base_url(base_url: str) -> str:
    """Switch only the API version, retaining the configured Sub2API host and Key."""
    base = base_url.rstrip("/")
    if base.endswith("/v1"):
        return base[:-3] + "/v1beta"
    if base.endswith("/v1beta"):
        return base
    return base + "/v1beta"


def normalize_gemini_base_url(value: str, *, https_only: bool = False) -> str:
    base = value.strip().rstrip("/")
    if base.endswith("/v1beta"):
        base = base[:-7] + "/v1"
    return gemini_base_url(normalize_base_url(base, https_only=https_only))


def validate_gemini_config(value: Any) -> ApiConfig:
    if not isinstance(value, dict):
        raise ConfigError("Gemini 专用配置必须为 JSON 对象")
    key = value.get("api_key")
    if not isinstance(key, str) or not key.strip() or any(not 33 <= ord(ch) <= 126 for ch in key.strip()):
        raise ConfigError("Gemini api_key 必须是非空 ASCII 字符串")
    url = normalize_gemini_base_url(value.get("base_url", GEMINI_DEFAULT_BASE_URL), https_only=True)
    return ApiConfig(url, key.strip(), "gemini-config", "gemini-config")


def load_gemini_config() -> ApiConfig | None:
    if not GEMINI_CONFIG_PATH.is_file():
        return None
    try:
        obj = json.loads(GEMINI_CONFIG_PATH.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ConfigError("无法读取 Gemini 独立配置文件") from exc
    if not isinstance(obj, dict) or obj.get("version") != 1:
        raise ConfigError("Gemini 独立配置文件版本不受支持")
    return validate_gemini_config(obj)


def configure_gemini(value: Any, *, replace: bool = False) -> dict[str, Any]:
    config = validate_gemini_config(value)
    if GEMINI_CONFIG_PATH.exists() and not replace:
        raise ConfigError("Gemini 配置已存在；需要更新时使用 --replace-config")
    body = json.dumps({"version": 1, "base_url": config.base_url, "api_key": config.api_key},
                      ensure_ascii=False, indent=2).encode("utf-8")
    try:
        atomic_write(GEMINI_CONFIG_PATH, body, replace=replace)
    except OSError as exc:
        raise ConfigError("无法写入 Gemini 独立配置") from exc
    return {"status": "saved", "version": VERSION, "provider": "gemini",
            "base_url": config.base_url, "config_path": str(GEMINI_CONFIG_PATH),
            "credential_status": "configured"}


def discover_gemini_config(home: Path) -> ApiConfig:
    """Independent Gemini key; optional per-provider URL, never reuse the GPT key."""
    values = read_skill_env()
    file_key = values.get("GEMINI_API_KEY", "").strip()
    file_url = values.get("GEMINI_BASE_URL", "").strip()
    local = load_gemini_config() if not file_key else None
    environment_key = os.environ.get("GEMINI_API_KEY", "").strip()
    key = file_key or (local.api_key if local else "") or environment_key
    if not key:
        raise ConfigError("Gemini 未配置 Key；请编辑 Skill 根目录 .env 的 GEMINI_API_KEY。不会复用 GPT API Key")
    configured_url, _ = config_base_url(home) if not file_url and not local else (None, None)
    environment_url = os.environ.get("GEMINI_BASE_URL", "").strip()
    base_url = ((local.base_url if local else "") or file_url or environment_url
                or configured_url or GEMINI_DEFAULT_BASE_URL)
    return ApiConfig(
        base_url=normalize_gemini_base_url(base_url),
        api_key=key,
        endpoint_source="gemini-config" if local else ".env" if file_url else "environment" if environment_url else "codex-provider" if configured_url else "default",
        credential_source=".env" if file_key else "gemini-config" if local else "environment",
    )


def gemini_config_report() -> dict[str, Any]:
    values = read_skill_env()
    file_key = bool(values.get("GEMINI_API_KEY", "").strip())
    environment_key = bool(os.environ.get("GEMINI_API_KEY", "").strip())
    stored = load_gemini_config() if not file_key else None
    return {
        "available": file_key or stored is not None or environment_key,
        "credential_source": ".env" if file_key else "gemini-config" if stored else "environment" if environment_key else "missing",
        "endpoint_source": "gemini-config" if stored else ".env" if values.get("GEMINI_BASE_URL", "").strip() else "environment" if os.environ.get("GEMINI_BASE_URL", "").strip() else "codex-provider",
    }


def gemini_json_body(prompt: str, images: list[Path], aspect_ratio: str | None,
                     image_size: str | None, thinking_level: str | None,
                     google_search: bool, image_only: bool) -> bytes:
    parts: list[dict[str, Any]] = [{"text": prompt}]
    for file in images:
        if not file.is_file():
            raise ConfigError(f"Input image not found: {file}")
        mime = mimetypes.guess_type(file.name)[0]
        if not mime or not mime.startswith("image/"):
            raise ConfigError(f"Input is not a recognized image file: {file}")
        parts.append({"inlineData": {
            "mimeType": mime, "data": base64.b64encode(file.read_bytes()).decode("ascii")
        }})
    generation_config: dict[str, Any] = {
        "responseModalities": ["IMAGE"] if image_only else ["TEXT", "IMAGE"]
    }
    image_config = {}
    if aspect_ratio:
        image_config["aspectRatio"] = aspect_ratio
    if image_size:
        image_config["imageSize"] = image_size
    if image_config:
        generation_config["imageConfig"] = image_config
    if thinking_level:
        generation_config["thinkingConfig"] = {"thinkingLevel": thinking_level}
    payload: dict[str, Any] = {
        "contents": [{"role": "user", "parts": parts}],
        "generationConfig": generation_config,
    }
    if google_search:
        payload["tools"] = [{"googleSearch": {}}]
    return json.dumps(payload, ensure_ascii=False).encode("utf-8")


def write_gemini_images(result: dict[str, Any], output: Path, output_format: str,
                        *, force: bool = False) -> dict[str, Any]:
    """Read native Gemini image parts; output-format is a local conversion."""
    candidates = result.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        raise ApiError("Gemini 响应没有 candidates", category="empty_image_result", http_status=200)
    content = candidates[0].get("content", {}) if isinstance(candidates[0], dict) else {}
    parts = content.get("parts", []) if isinstance(content, dict) else []
    if not isinstance(parts, list):
        parts = []
    blobs = []
    for part in parts:
        if not isinstance(part, dict) or part.get("thought"):
            continue
        inline = part.get("inlineData") or part.get("inline_data")
        if isinstance(inline, dict) and str(inline.get("mimeType", inline.get("mime_type", ""))).startswith("image/"):
            if isinstance(inline.get("data"), str) and inline["data"]:
                blobs.append(inline["data"])
    if not blobs:
        raise ApiError("Gemini 响应没有图片 inlineData", category="empty_image_result",
                       http_status=200, action="检查模型权限、分组与上游响应，不自动重复生图")
    Image = image_runtime()
    saved = []
    for index, encoded in enumerate(blobs):
        with Image.open(io.BytesIO(decode_image(encoded))) as image:
            converted = image.convert("RGB") if output_format == "jpeg" else image
            stream = io.BytesIO()
            converted.save(stream, format={"png": "PNG", "jpeg": "JPEG", "webp": "WEBP"}[output_format])
        destination = output if index == 0 else output.with_name(f"{output.stem}-{index+1}{output.suffix}")
        saved.append({"output": str(destination), **save_image_bytes(stream.getvalue(), destination, force=force)})
    return {**saved[0], "image_count": len(saved), "outputs": [item["output"] for item in saved],
            "markdown": "\n".join(item["markdown"] for item in saved)}


def resolve_request_options(prompt: str | None, model: str | None, quality: str | None,
                            size: str | None, preset: str | None,
                            background: str | None = None,
                            output_format: str | None = None) -> tuple[str, str, str, str, str, str, str]:
    preset_name = preset or "auto"
    values = PRESET_OPTIONS.get(preset_name)
    if values is None:
        raise ConfigError("不支持的 preset；可选：" + "、".join(PRESET_OPTIONS))
    selected_prompt = prompt.strip() if isinstance(prompt, str) and prompt.strip() else values.get("prompt", "")
    if not selected_prompt:
        raise ConfigError("--prompt is required unless the selected preset supplies one")
    selected_model = model or values.get("model") or DEFAULT_MODEL
    selected_quality = quality or values.get("quality") or ("high" if selected_model == "gpt-image-2.5-sunburst" else DEFAULT_QUALITY)
    selected_size = size or values.get("size") or DEFAULT_SIZE
    selected_background = background or values.get("background") or DEFAULT_BACKGROUND
    selected_output_format = output_format or values.get("output_format") or (
        "png" if selected_background == "transparent" else DEFAULT_OUTPUT_FORMAT
    )
    validate_model_options(selected_model, selected_quality)
    validate_output_options(selected_background, selected_output_format)
    return (selected_prompt, selected_model, selected_quality, selected_size, preset_name,
            selected_background, selected_output_format)


def validate_model_options(model: str, quality: str) -> str:
    if model not in SUPPORTED_MODELS:
        raise ConfigError("不支持的生图模型；可选：" + "、".join(SUPPORTED_MODELS))
    if model == GEMINI_MODEL:
        return model
    if quality not in MODEL_QUALITIES[model]:
        allowed = "/".join(sorted(MODEL_QUALITIES[model]))
        raise ConfigError(f"{model} 不支持 quality={quality}；可选：{allowed}")
    return model


def validate_output_options(background: str, output_format: str) -> None:
    if background not in BACKGROUND_OPTIONS:
        raise ConfigError("不支持的 background；可选：" + "/".join(BACKGROUND_OPTIONS))
    if output_format not in OUTPUT_FORMATS:
        raise ConfigError("不支持的 output_format；可选：" + "/".join(OUTPUT_FORMATS))
    if background == "transparent" and output_format == "jpeg":
        raise ConfigError("透明背景必须使用 output_format=png 或 webp，不能使用 jpeg")


def json_body(prompt: str, size: str, quality: str, model: str = DEFAULT_MODEL,
              background: str = DEFAULT_BACKGROUND, output_format: str = DEFAULT_OUTPUT_FORMAT) -> bytes:
    validate_model_options(model, quality)
    validate_output_options(background, output_format)
    return json.dumps(
        {"model": model, "prompt": prompt, "size": size, "quality": quality, "background": background,
         "output_format": output_format, "n": 1},
        ensure_ascii=False,
    ).encode("utf-8")


def multipart_body(prompt: str, images: list[Path], size: str, quality: str,
                   model: str = DEFAULT_MODEL, background: str = DEFAULT_BACKGROUND,
                   output_format: str = DEFAULT_OUTPUT_FORMAT) -> tuple[bytes, str]:
    validate_model_options(model, quality)
    validate_output_options(background, output_format)
    boundary = f"----codex-image-{secrets.token_hex(16)}"
    chunks: list[bytes] = []

    def field(name: str, value: str) -> None:
        chunks.extend([
            f"--{boundary}\r\n".encode(),
            f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode(),
            value.encode("utf-8"),
            b"\r\n",
        ])

    field("model", model)
    field("prompt", prompt)
    field("size", size)
    field("quality", quality)
    field("background", background)
    field("output_format", output_format)
    field("n", "1")

    for image in images:
        if not image.is_file():
            raise ConfigError(f"Input image not found: {image}")
        mime = mimetypes.guess_type(image.name)[0] or "application/octet-stream"
        chunks.extend([
            f"--{boundary}\r\n".encode(),
            (f'Content-Disposition: form-data; name="image"; filename="{image.name}"\r\n').encode("utf-8"),
            f"Content-Type: {mime}\r\n\r\n".encode(),
            image.read_bytes(),
            b"\r\n",
        ])
    chunks.append(f"--{boundary}--\r\n".encode())
    return b"".join(chunks), f"multipart/form-data; boundary={boundary}"


def default_output(model: str = DEFAULT_MODEL, output_format: str = DEFAULT_OUTPUT_FORMAT) -> Path:
    # Keep the caller's project cwd; never silently store images inside the installed skill.
    if Path.cwd().resolve().is_relative_to(SKILL_ROOT.resolve()):
        raise ConfigError("默认输出不能位于技能目录；请从当前项目目录运行，或显式指定 --out")
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    return Path("output/imagegen") / f"{model}-{stamp}-{secrets.token_hex(4)}{OUTPUT_SUFFIXES[output_format]}"


def ensure_output(path: Path, force: bool) -> Path:
    output = path.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists() and not force:
        raise ConfigError(f"Output already exists; choose a new path or pass --force: {output}")
    return output


def image_runtime():
    try:
        from PIL import Image
    except ImportError as exc:
        raise ConfigError("图片验证需要 Pillow；Desktop 使用 bundled Python，其他环境安装 requirements.txt 后再请求") from exc
    return Image


def atomic_write(path: Path, data: bytes, *, replace: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temp = Path(name)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        if replace:
            os.replace(temp, path)
        else:
            # Publish atomically without overwriting an existing file (including a racing writer).
            os.link(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def image_markdown(output: Path) -> str:
    # Angle brackets keep spaces and parentheses in an absolute path inside one image link.
    path = output.expanduser().resolve().as_posix().replace("<", "%3C").replace(">", "%3E")
    return f"![生成的图片](<{path}>)"


def save_image_bytes(data: bytes, output: Path, *, force: bool = False, require_alpha: bool = False) -> dict[str, Any]:
    Image = image_runtime()
    try:
        with Image.open(io.BytesIO(data)) as image:
            image.verify()
        with Image.open(io.BytesIO(data)) as image:
            image.load()
            bands = image.getbands()
            has_alpha = "A" in bands
            alpha_min = alpha_max = None
            if has_alpha:
                alpha_min, alpha_max = image.getchannel("A").getextrema()
            metadata = {"width": image.width, "height": image.height, "image_format": image.format,
                        "image_mode": image.mode, "bands": bands, "has_alpha": has_alpha,
                        "alpha_min": alpha_min, "alpha_max": alpha_max}
    except Exception as exc:
        raise ApiError("图片不能完整解码，未写入输出文件", category="invalid_image",
                       cause="图片数据损坏或内容并非图片", action="保留已有响应并排查交付，不重新生成", outcome="delivery_failed") from exc
    if require_alpha and (not metadata["has_alpha"] or metadata["alpha_min"] == 255):
        raise ApiError("请求了透明背景，但返回图片没有可见透明像素，未写入输出文件",
                       category="invalid_transparency", outcome="delivery_failed",
                       cause="上游或中转服务可能未透传 background/output_format",
                       action="检查实际请求体和中转参数白名单，不重新生成")
    try:
        atomic_write(output, data, replace=force)
    except OSError as exc:
        raise ApiError("已有图片数据，但保存失败（文件已存在、权限或磁盘问题）", category="image_save_error",
                       cause="本地交付失败，不是生图失败", action="更换输出位置或明确允许覆盖，再恢复同一产物", outcome="generated") from exc
    return {**metadata, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(),
            "markdown": image_markdown(output)}


def decode_image(encoded: str) -> bytes:
    try:
        return base64.b64decode(encoded, validate=True)
    except (ValueError, TypeError) as exc:
        raise ApiError("图片 Base64 数据无效", category="invalid_image", outcome="delivery_failed",
                       action="检查原始结果是否完整，不重新生成") from exc


def write_image(result: dict[str, Any], output: Path, *, force: bool = False, require_alpha: bool = False) -> dict[str, Any]:
    error = upstream_error(result)
    if error:
        raise error
    data = result.get("data")
    if not isinstance(data, list) or not data or not isinstance(data[0], dict):
        raise ApiError("响应未包含 data[0] 图片", category="empty_image_result", http_status=200,
                       action="核对调用记录和完整响应，不能当作成功或自动重发")
    item = data[0]
    error = upstream_error(item)
    if error:
        raise error
    encoded = item.get("b64_json")
    if isinstance(encoded, str) and encoded:
        return save_image_bytes(decode_image(encoded), output, force=force, require_alpha=require_alpha)
    image_url = item.get("url")
    if isinstance(image_url, str) and image_url:
        parsed = urllib.parse.urlsplit(image_url)
        if parsed.scheme not in {"https", "http"} or not parsed.hostname or parsed.username or parsed.password:
            raise ApiError("图片 URL 无效", category="invalid_image_url", outcome="delivery_failed")
        # Signed image URLs may contain queries, but are never logged and receive no API Authorization.
        try:
            content, _ = request_bytes(urllib.request.Request(image_url))
        except ApiError as exc:
            exc.report["outcome"] = "delivery_failed"
            exc.report["suggested_action"] = "只重取已有图片或恢复本地产物，不重新生成"
            raise
        return save_image_bytes(content, output, force=force, require_alpha=require_alpha)
    raise ApiError("响应没有 b64_json 或图片 URL", category="empty_image_result", http_status=200,
                   action="核对已生成产物，不自动重试")


def recover_native(session_file: Path, call_id: str, output: Path, *, force: bool = False) -> dict[str, Any]:
    # Only inspect the explicitly supplied current-task file and exact image call ID.
    # Prompt text containing a fake result is not a response_item and cannot be recovered.
    matched = None
    try:
        with session_file.open(encoding="utf-8-sig") as stream:
            for line in stream:
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue  # A live session can end with an incomplete JSONL record.
                if not isinstance(record, dict) or record.get("type") != "response_item":
                    continue
                item = record.get("payload")
                if not isinstance(item, dict) or item.get("type") != "image_generation_call" or item.get("id") != call_id:
                    continue
                matched = item
                if isinstance(item.get("result"), str) and item["result"]:
                    metadata = save_image_bytes(decode_image(item["result"]), output, force=force)
                    return {"version": VERSION, "mode": "native-recovery", "call_id": call_id,
                            "output": str(output), "status": "ok", **metadata}
    except OSError as exc:
        raise ConfigError("无法读取指定会话文件；不搜索其他任务") from exc
    if matched and matched.get("status") == "failed":
        error = upstream_error(matched)
        if error:
            error.report["outcome"] = "failed"
            raise error
    raise ApiError("指定调用没有可恢复的完整图片数据", category="native_result_unknown",
                   cause="记录未写完、产物缺失或结果未知，可能已计费",
                   action="检查当前调用状态与已有产物；不自动重新生成")


def validate_fallback(value: Any) -> ApiConfig:
    if not isinstance(value, dict):
        raise ConfigError("专用配置必须是 JSON 对象")
    key = value.get("api_key")
    if not isinstance(key, str) or not key.strip() or any(not 33 <= ord(c) <= 126 for c in key.strip()):
        raise ConfigError("api_key 必须为非空、无内部空白的 ASCII 字符串；未展示输入内容")
    base_url = normalize_base_url(value.get("base_url", FALLBACK_BASE_URL), https_only=True)
    return ApiConfig(base_url, key.strip(), "fallback-config", "fallback-config")


def load_fallback(path: Path | None = None) -> ApiConfig:
    path = path or FALLBACK_PATH
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ConfigError("第三模式配置缺失或无效，请先运行 configure-fallback") from exc
    if not isinstance(value, dict) or value.get("version") != 1:
        raise ConfigError("第三模式配置版本不受支持")
    return validate_fallback(value)


def configure_fallback(value: Any, *, replace: bool = False, path: Path | None = None) -> dict[str, Any]:
    path = path or FALLBACK_PATH
    config = validate_fallback(value)
    if path.exists() and not replace:
        raise ConfigError("第三模式配置已存在；用户确认替换后才能使用 --replace-config")
    content = json.dumps({"version": 1, "base_url": config.base_url, "api_key": config.api_key}, ensure_ascii=False, indent=2) + "\n"
    try:
        atomic_write(path, content.encode("utf-8"), replace=replace)
    except OSError as exc:
        raise ConfigError("无法保存第三模式配置，未建立含密钥的历史备份") from exc
    return {"status": "saved", "version": VERSION, "mode": "fallback", "base_url": config.base_url,
            "credential_status": "configured", "config_path": str(path), "endpoint_verified": False,
            "warning": "配置为明文，聊天中的 Key 可能留在历史中；复制技能目录可能泄露凭证"}


def fallback_report() -> dict[str, Any]:
    if not FALLBACK_PATH.exists():
        return {"available": False, "base_url": FALLBACK_BASE_URL + "/v1", "credential_status": "missing", "endpoint_source": "fallback-config"}
    try:
        config = load_fallback()
        return {"available": True, "base_url": config.base_url, "credential_status": "configured", "endpoint_source": config.endpoint_source}
    except ConfigError as exc:
        return {"available": False, "credential_status": "invalid", "error": exc.report}


def existing_config_report(home: Path) -> dict[str, Any]:
    values = read_skill_env()
    configured_url, provider_name = config_base_url(home)
    local_url = values.get("OPENAI_BASE_URL", "").strip()
    env_url = os.environ.get("OPENAI_BASE_URL", "").strip()
    endpoint = local_url or configured_url or env_url or DEFAULT_BASE_URL
    local_key = bool(values.get("OPENAI_API_KEY", "").strip())
    env_key = bool(os.environ.get("OPENAI_API_KEY", "").strip())
    file_key = False
    auth_error = None
    if not local_key:
        try:
            file_key = bool(auth_file_key(home))
        except ConfigError as exc:
            auth_error = str(exc)
    return {
        "version": VERSION,
        "model": DEFAULT_MODEL,
        "default_model": DEFAULT_MODEL,
        "available_models": list(SUPPORTED_MODELS),
        "available_presets": list(PRESET_OPTIONS),
        "fallback_mode": fallback_report(),
        "native_mode": {
            "available": "detected-by-codex-runtime",
            "requires_auth_json": False,
        },
        "api_mode": {
            "available": local_key or file_key or env_key,
            "credential_source": ".env" if local_key else "auth.json" if file_key else "environment" if env_key else "missing",
            "endpoint_source": ".env" if local_url else "config.toml" if configured_url else "environment" if env_url else "official-default",
            "endpoint_host": endpoint_host(normalize_base_url(endpoint)),
            "base_url": normalize_base_url(endpoint),
            "credential_status": "configured" if local_key or file_key or env_key else "missing",
            "provider": provider_name,
            "auth_error": auth_error,
        },
    }


def config_report(home: Path) -> dict[str, Any]:
    try:
        return existing_config_report(home)
    except ConfigError as exc:
        return {"version": VERSION, "model": DEFAULT_MODEL, "default_model": DEFAULT_MODEL, "available_models": list(SUPPORTED_MODELS), "available_presets": list(PRESET_OPTIONS),
                "native_mode": {"available": "detected-by-codex-runtime", "requires_auth_json": False},
                "api_mode": {"available": False, "credential_status": "invalid", "error": exc.report},
                "fallback_mode": fallback_report()}


class SafeArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        error = ConfigError("命令参数无效；使用 --help 查看用法。Key 只允许通过标准输入传入")
        self.exit(2, "CONFIG_ERROR: " + str(error) + "\n")


def build_parser() -> argparse.ArgumentParser:
    parser = SafeArgumentParser(description="One-command GPT Image generation/edit with direct project output")
    parser.add_argument("command", choices=("run", "generate", "edit", "list-models", "config-check", "version", "configure-fallback", "configure-gemini", "recover-native"))
    parser.add_argument("--prompt", help="Generation or edit instruction")
    parser.add_argument("--image", action="append", help="Input image for edit; may be repeated")
    parser.add_argument("--preset", choices=tuple(PRESET_OPTIONS), default=None, help="auto, fast, final, text-heavy, or benchmark-t2i")
    parser.add_argument("--size", default=None, help="1024x1024, 1536x1024, 1024x1536, or auto")
    parser.add_argument("--quality", choices=("low", "medium", "high", "xhigh", "max", "auto"), default=None)
    parser.add_argument("--background", choices=BACKGROUND_OPTIONS, default=None, help="auto, transparent, or opaque")
    parser.add_argument("--output-format", choices=OUTPUT_FORMATS, default=None, help="png, jpeg, or webp")
    parser.add_argument("--model", default=None, help="Explicit image model; overrides preset")
    parser.add_argument("--aspect-ratio", choices=GEMINI_ASPECT_RATIOS, help="Gemini imageConfig.aspectRatio")
    parser.add_argument("--image-size", choices=GEMINI_IMAGE_SIZES, help="Gemini imageConfig.imageSize")
    parser.add_argument("--thinking-level", choices=("minimal", "medium", "high"), help="Gemini thinkingConfig.thinkingLevel")
    parser.add_argument("--google-search", action="store_true", help="Gemini Google Search grounding")
    parser.add_argument("--image-only", action="store_true", help="Gemini responseModalities=[IMAGE]")
    parser.add_argument("--out", type=Path, default=None, help="Output image path; defaults to project output/imagegen/")
    parser.add_argument("--force", action="store_true", help="Allow replacing an existing output")
    parser.add_argument("--config-source", choices=("existing", "fallback"), default="existing")
    parser.add_argument("--replace-config", action="store_true", help="Replace fallback config only after user confirmation")
    parser.add_argument("--session-file", type=Path, help="Exact current-task session JSONL; exceptional recovery only")
    parser.add_argument("--call-id", help="Exact image_generation_call ID; exceptional recovery only")
    parser.add_argument("--config-home", type=Path, default=None, help=argparse.SUPPRESS)
    return parser


def main() -> int:
    # Keep exit codes: 0 success, 2 local/config error, 1 upstream/delivery error.
    # argparse prints unknown arguments verbatim by default; suppress that to avoid echoing a Key.
    parser = build_parser()
    args = parser.parse_args()
    active_key = ""
    try:
        if args.command == "version":
            print(VERSION)
            return 0
        if args.command == "config-check":
            report = {"version": VERSION, "fallback_mode": fallback_report()} if args.config_source == "fallback" else config_report((args.config_home or codex_home()).expanduser().resolve())
            report["gemini_mode"] = gemini_config_report()
            print(json.dumps(report, ensure_ascii=False))
            return 0
        if args.command in ("configure-fallback", "configure-gemini"):
            try:
                raw_config = sys.stdin.read(16385)
                if len(raw_config) > 16384:
                    raise ConfigError("配置输入过长，未保存或回显输入内容")
                value = json.loads(raw_config)
            except (json.JSONDecodeError, UnicodeError) as exc:
                raise ConfigError("标准输入须提供 JSON 配置对象，未回显输入内容") from exc
            configured = (configure_gemini(value, replace=args.replace_config)
                          if args.command == "configure-gemini" else
                          configure_fallback(value, replace=args.replace_config))
            print(json.dumps(configured, ensure_ascii=False))
            return 0
        if args.command == "recover-native":
            if not args.session_file or not args.call_id or not args.out:
                raise ConfigError("recover-native 需要 --session-file、--call-id 和 --out")
            image_runtime()
            output = ensure_output(args.out, args.force)
            print(json.dumps(recover_native(args.session_file, args.call_id, output, force=args.force), ensure_ascii=False))
            return 0
        if args.command == "list-models":
            config = discover_gemini_config((args.config_home or codex_home()).expanduser().resolve())
            active_key = config.api_key
            result = api_request(config.base_url + "/models", config.api_key, method="GET")
            if not isinstance(result.get("models"), list):
                raise ApiError("Gemini 模型列表响应缺少 models 数组", category="invalid_response")
            print(json.dumps({"models": result["models"], "nextPageToken": result.get("nextPageToken"),
                              "endpoint_host": endpoint_host(config.base_url)}, ensure_ascii=False))
            return 0
        (prompt, selected_model, selected_quality, selected_size, selected_preset,
         selected_background, selected_output_format) = resolve_request_options(
            args.prompt, args.model, args.quality, args.size, args.preset,
            args.background, args.output_format
        )
        operation = "edit" if args.command == "edit" or (args.command == "run" and args.image) else "generate"
        if operation == "edit" and not args.image:
            raise ConfigError("--image is required for edit")
        if selected_model != GEMINI_MODEL and (
            args.aspect_ratio or args.image_size or args.thinking_level or args.google_search or args.image_only
        ):
            raise ConfigError("Gemini 专用参数只能与 gemini-nano-banana-2.1 一起使用")
        if selected_model == GEMINI_MODEL and (
            args.quality is not None or args.size is not None or selected_background != "auto"
        ):
            raise ConfigError("Gemini 不支持 OpenAI --quality/--size/--background；请用 --aspect-ratio 和 --image-size")
        image_runtime()  # Check dependency before a possibly billable POST.
        output = ensure_output(args.out or default_output(selected_model, selected_output_format), args.force)
        home = (args.config_home or codex_home()).expanduser().resolve()
        config = (discover_gemini_config(home) if selected_model == GEMINI_MODEL
                  else load_fallback() if args.config_source == "fallback"
                  else discover_api_config(home))
        active_key = config.api_key
        if selected_model == GEMINI_MODEL:
            paths = [Path(value).expanduser().resolve() for value in (args.image or [])]
            body = gemini_json_body(prompt, paths, args.aspect_ratio, args.image_size,
                                    args.thinking_level, args.google_search, args.image_only)
            route_url = f"{config.base_url}/models/{GEMINI_MODEL}:generateContent"
            operation = "edit" if paths else "generate"
            content_type = "application/json; charset=utf-8"
        elif operation == "generate":
            body = json_body(prompt, selected_size, selected_quality, selected_model, selected_background, selected_output_format)
            content_type = "application/json; charset=utf-8"
            route_url = f"{config.base_url}/images/generations"
        else:
            paths = [Path(value).expanduser().resolve() for value in args.image]
            body, content_type = multipart_body(prompt, paths, selected_size, selected_quality, selected_model, selected_background, selected_output_format)
            route_url = f"{config.base_url}/images/edits"
        started = time.perf_counter()
        result = api_request(route_url, config.api_key, body, content_type)
        metadata = (write_gemini_images(result, output, selected_output_format, force=args.force)
                    if selected_model == GEMINI_MODEL else
                    write_image(result, output, force=args.force, require_alpha=(selected_background == "transparent")))
        elapsed_ms = round((time.perf_counter() - started) * 1000)
        print(json.dumps({
            "version": VERSION, "model": selected_model, "quality": selected_quality, "size": selected_size,
            "background": selected_background, "output_format": selected_output_format,
            "api_protocol": "gemini-v1beta" if selected_model == GEMINI_MODEL else "openai-images",
            "operation": operation, "preset": selected_preset,
            "mode": "fallback" if args.config_source == "fallback" else "api",
            "endpoint_host": endpoint_host(config.base_url), "endpoint_source": config.endpoint_source,
            "credential_source": config.credential_source, "output": str(output), "status": "ok", "delivery_required": True, "delivery_instruction": "立即将 output 对应的图片嵌入当前 Codex 回复；未嵌入图片前不得结束对话。", "user_status": f"图片生成请求已发送，使用模型{selected_model}正在绘图中，请稍后 ",
            "elapsed_ms": elapsed_ms, **metadata,
        }, ensure_ascii=False))
        return 0
    except SkillError as exc:
        prefix = "CONFIG_ERROR" if isinstance(exc, ConfigError) else "API_ERROR"
        # Re-render the report: download/recovery may refine the outcome after initial classification.
        print(prefix + ": " + redact(json.dumps(exc.report, ensure_ascii=False), (active_key,)), file=sys.stderr)
        return 2 if isinstance(exc, ConfigError) else 1
    except Exception:
        error = ApiError("发生未分类错误，未输出可能含凭证的异常内容", category="unexpected_error")
        print("UNEXPECTED_ERROR: " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
